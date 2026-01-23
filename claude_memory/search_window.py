"""
Search window UI for Claude Memory app.
Built with tkinter for lightweight, no-dependency UI.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
from typing import Optional, List

from . import constants
from .database import search_entries, get_categories, get_entry_by_id, get_recent_entries, delete_entry, add_entry
from .ai_query import summarize_search_results, NoAPIKeyError, AIQueryError
from .pdf_handler import (
    is_pdf_support_available, import_pdf, render_all_pages,
    get_pdf_page_count, HAS_PIL
)

# Import PIL for PDF display
if HAS_PIL:
    from PIL import ImageTk


class SearchWindow:
    """
    Search window with query input, filters, results list, and detail view.
    Shows/hides rather than creating/destroying for better performance.
    """

    def __init__(self, on_chat: callable = None, chat_window=None):
        self._on_chat = on_chat
        self._chat_window = chat_window  # Reference to ChatWindow for "Chat These"
        self._root: Optional[tk.Tk] = None
        self._results: list[dict] = []
        self._selected_entry: Optional[dict] = None

        # Widget references
        self._search_var: Optional[tk.StringVar] = None
        self._category_var: Optional[tk.StringVar] = None
        self._date_var: Optional[tk.StringVar] = None
        self._results_listbox: Optional[tk.Listbox] = None
        self._detail_text: Optional[scrolledtext.ScrolledText] = None
        self._meta_label: Optional[tk.Label] = None

        # Auto-refresh state
        self._auto_refresh_job = None
        self._last_entry_id = 0  # Track newest entry to detect changes

        # Multi-select state
        self._multi_select_var: Optional[tk.BooleanVar] = None
        self._delete_selected_btn: Optional[ttk.Button] = None
        self._remove_duplicates_btn: Optional[ttk.Button] = None
        self._multi_select_notice: Optional[tk.Label] = None
        self._check_vars: dict = {}  # Maps index to BooleanVar for checkboxes
        self._checkbox_frame: Optional[tk.Frame] = None
        self._checkbox_canvas: Optional[tk.Canvas] = None

        # PDF viewer state
        self._pdf_canvas: Optional[tk.Canvas] = None
        self._pdf_images: List = []  # Store PhotoImage references to prevent garbage collection
        self._pdf_frame: Optional[tk.Frame] = None

    def _create_window(self) -> None:
        """Create the search window."""
        self._root = tk.Toplevel()
        self._root.title(f"{constants.APP_NAME} - Search")
        self._root.geometry(
            f"{constants.SEARCH_WINDOW_WIDTH}x{constants.SEARCH_WINDOW_HEIGHT}"
        )

        # Handle window close - hide instead of destroy
        self._root.protocol("WM_DELETE_WINDOW", self.hide)

        # Configure grid weights for resizing
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(2, weight=1)

        self._create_search_bar()
        self._create_filters()
        self._create_results_area()

        # Bind Enter key to search
        self._root.bind("<Return>", lambda e: self._do_search())

        # Bind F5 to refresh
        self._root.bind("<F5>", lambda e: self._refresh())

        # Bind Escape to hide
        self._root.bind("<Escape>", lambda e: self.hide())

        # Bind Ctrl+V to quick add (when not in a text widget)
        self._root.bind("<Control-v>", self._on_ctrl_v)

    def _create_search_bar(self) -> None:
        """Create the search input area."""
        frame = ttk.Frame(self._root, padding="10 10 10 5")
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(
            frame, textvariable=self._search_var, font=("Segoe UI", 12)
        )
        search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        search_entry.focus()

        search_btn = ttk.Button(frame, text="Search", command=self._do_search)
        search_btn.grid(row=0, column=1, padx=(0, 5))

        refresh_btn = ttk.Button(frame, text="Refresh", command=self._refresh)
        refresh_btn.grid(row=0, column=2, padx=(0, 5))

        self._ai_btn = ttk.Button(frame, text="AI Summarize", command=self._do_ai_summarize)
        self._ai_btn.grid(row=0, column=3, padx=(0, 5))

        chat_btn = ttk.Button(frame, text="AI Chat", command=self._open_chat)
        chat_btn.grid(row=0, column=4, padx=(0, 5))

        # Chat about current search results only
        self._chat_these_btn = ttk.Button(frame, text="Chat These", command=self._chat_about_results)
        self._chat_these_btn.grid(row=0, column=5)

        # Quick Add button (Ctrl+V shortcut)
        add_btn = ttk.Button(frame, text="+ Add", command=self._show_quick_add)
        add_btn.grid(row=0, column=6, padx=(10, 0))

        # Import PDF button
        if is_pdf_support_available():
            pdf_btn = ttk.Button(frame, text="Import PDF", command=self._import_pdf)
            pdf_btn.grid(row=0, column=7, padx=(5, 0))

    def _create_filters(self) -> None:
        """Create the filter dropdowns."""
        frame = ttk.Frame(self._root, padding="10 5 10 5")
        frame.grid(row=1, column=0, sticky="ew")

        # Category filter
        ttk.Label(frame, text="Category:").pack(side=tk.LEFT, padx=(0, 5))
        self._category_var = tk.StringVar(value="All")
        category_combo = ttk.Combobox(
            frame,
            textvariable=self._category_var,
            values=["All"],
            state="readonly",
            width=15,
        )
        category_combo.pack(side=tk.LEFT, padx=(0, 20))
        category_combo.bind("<<ComboboxSelected>>", lambda e: self._do_search())

        # Date filter
        ttk.Label(frame, text="Date:").pack(side=tk.LEFT, padx=(0, 5))
        self._date_var = tk.StringVar(value="All Time")
        date_combo = ttk.Combobox(
            frame,
            textvariable=self._date_var,
            values=list(constants.DATE_FILTERS.keys()),
            state="readonly",
            width=12,
        )
        date_combo.pack(side=tk.LEFT)
        date_combo.bind("<<ComboboxSelected>>", lambda e: self._do_search())

        # Separator
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=15)

        # Multi-select checkbox
        self._multi_select_var = tk.BooleanVar(value=False)
        multi_check = ttk.Checkbutton(
            frame,
            text="Multi-Select",
            variable=self._multi_select_var,
            command=self._toggle_multi_select
        )
        multi_check.pack(side=tk.LEFT, padx=(0, 10))

        # Delete Selected button (hidden until multi-select enabled)
        self._delete_selected_btn = ttk.Button(
            frame, text="Delete Selected", command=self._delete_multiple
        )
        self._delete_selected_btn.pack(side=tk.LEFT)
        self._delete_selected_btn.pack_forget()  # Hide initially

        # Remove Duplicates button (hidden until multi-select enabled)
        self._remove_duplicates_btn = ttk.Button(
            frame, text="Remove Duplicates", command=self._remove_duplicates
        )
        self._remove_duplicates_btn.pack(side=tk.LEFT, padx=(5, 0))
        self._remove_duplicates_btn.pack_forget()  # Hide initially

        # Results count label
        self._count_label = ttk.Label(frame, text="")
        self._count_label.pack(side=tk.RIGHT)

    def _create_results_area(self) -> None:
        """Create the results list and detail view."""
        # Main paned window for resizable split
        paned = ttk.PanedWindow(self._root, orient=tk.HORIZONTAL)
        paned.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))

        # Left side: results list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        # Listbox with scrollbar
        self._results_listbox = tk.Listbox(
            left_frame,
            font=("Segoe UI", 10),
            selectmode=tk.SINGLE,
            activestyle="none",
        )
        self._results_listbox.grid(row=0, column=0, sticky="nsew")

        self._listbox_scrollbar = ttk.Scrollbar(
            left_frame, orient=tk.VERTICAL, command=self._results_listbox.yview
        )
        self._listbox_scrollbar.grid(row=0, column=1, sticky="ns")
        self._results_listbox.config(yscrollcommand=self._listbox_scrollbar.set)

        self._results_listbox.bind("<<ListboxSelect>>", self._on_select)
        self._results_listbox.bind("<Double-Button-1>", self._on_double_click)

        # Checkbox view (shown when multi-select is active)
        self._checkbox_canvas = tk.Canvas(left_frame, bg="white")
        self._checkbox_scrollbar = ttk.Scrollbar(
            left_frame, orient=tk.VERTICAL, command=self._checkbox_canvas.yview
        )
        self._checkbox_frame = ttk.Frame(self._checkbox_canvas)
        self._checkbox_canvas.configure(yscrollcommand=self._checkbox_scrollbar.set)

        # Create window in canvas
        self._checkbox_canvas_window = self._checkbox_canvas.create_window(
            (0, 0), window=self._checkbox_frame, anchor="nw"
        )

        # Bind resize
        self._checkbox_frame.bind("<Configure>", lambda e: self._checkbox_canvas.configure(
            scrollregion=self._checkbox_canvas.bbox("all")
        ))
        self._checkbox_canvas.bind("<Configure>", self._on_checkbox_canvas_resize)

        # Don't grid yet - shown when multi-select is enabled

        # Right side: detail view
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Header row with metadata and delete button
        header_frame = ttk.Frame(right_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        header_frame.columnconfigure(0, weight=1)

        # Metadata label
        self._meta_label = ttk.Label(
            header_frame, text="", font=("Segoe UI", 9), foreground="gray"
        )
        self._meta_label.grid(row=0, column=0, sticky="w")

        # Delete button (hidden until entry selected)
        self._delete_btn = ttk.Button(
            header_frame, text="Delete", command=self._delete_selected, width=8
        )
        self._delete_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self._delete_btn.grid_remove()  # Hide initially

        # Multi-select notice (shown when multi-select is active)
        self._multi_select_notice = tk.Label(
            right_frame,
            text="⚠ Multi-select mode is active\nUncheck Multi-select to view entry details",
            font=("Segoe UI", 11, "bold"),
            fg="#ff6600",  # Orange color
            bg="#fff3e0",  # Light orange background
            pady=20,
            relief=tk.RIDGE,
            borderwidth=2
        )
        # Don't grid it yet - shown when multi-select is enabled

        # Detail text area (for non-PDF entries)
        self._detail_text = scrolledtext.ScrolledText(
            right_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self._detail_text.grid(row=1, column=0, sticky="nsew")

        # PDF viewer frame (hidden by default, shown for PDF entries)
        self._pdf_frame = ttk.Frame(right_frame)
        # Don't grid it yet - it will be shown when needed

        # Create canvas with scrollbar for PDF pages
        self._pdf_canvas = tk.Canvas(self._pdf_frame, bg="gray")
        pdf_scrollbar = ttk.Scrollbar(self._pdf_frame, orient=tk.VERTICAL, command=self._pdf_canvas.yview)
        self._pdf_canvas.configure(yscrollcommand=pdf_scrollbar.set)

        self._pdf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pdf_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Inner frame to hold PDF page images
        self._pdf_inner_frame = ttk.Frame(self._pdf_canvas)
        self._pdf_canvas_window = self._pdf_canvas.create_window((0, 0), window=self._pdf_inner_frame, anchor="nw")

        # Bind mouse wheel for scrolling
        def _on_mousewheel(event):
            self._pdf_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self._pdf_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Update scroll region when inner frame changes
        def _configure_scroll(event):
            self._pdf_canvas.configure(scrollregion=self._pdf_canvas.bbox("all"))

        self._pdf_inner_frame.bind("<Configure>", _configure_scroll)

        # Resize canvas window when canvas is resized
        def _configure_canvas(event):
            self._pdf_canvas.itemconfig(self._pdf_canvas_window, width=event.width)

        self._pdf_canvas.bind("<Configure>", _configure_canvas)

    def _refresh_categories(self) -> None:
        """Refresh the category dropdown with current categories."""
        try:
            categories = ["All"] + get_categories()
            # Find the category combobox
            for widget in self._root.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Combobox):
                            if child.cget("textvariable") == str(self._category_var):
                                child["values"] = categories
                                break
        except Exception:
            pass

    def _refresh(self) -> None:
        """Refresh categories and re-run current search."""
        self._refresh_categories()
        self._do_search()

    def _start_auto_refresh(self) -> None:
        """Start auto-refresh timer to check for new entries."""
        self._stop_auto_refresh()  # Cancel any existing timer
        self._check_for_updates()

    def _stop_auto_refresh(self) -> None:
        """Stop auto-refresh timer."""
        if self._auto_refresh_job and self._root:
            self._root.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None

    def _check_for_updates(self) -> None:
        """Check if new entries exist and refresh if needed."""
        if not self._root or not self._root.winfo_exists():
            return

        try:
            # Get the most recent entry
            recent = get_recent_entries(limit=1)
            if recent:
                newest_id = recent[0]['id']
                if newest_id > self._last_entry_id:
                    self._last_entry_id = newest_id
                    self._refresh_categories()
                    self._do_search()
        except Exception:
            pass

        # Schedule next check in 2 seconds
        self._auto_refresh_job = self._root.after(2000, self._check_for_updates)

    def _do_search(self) -> None:
        """Execute the search with current filters."""
        query = self._search_var.get().strip()
        category = self._category_var.get()
        date_filter = self._date_var.get()

        # Get days from date filter
        days = constants.DATE_FILTERS.get(date_filter)

        # Category filter
        cat = None if category == "All" else category

        # DEBUG
        print(f"DEBUG _do_search: query='{query}', category='{cat}', days={days}")

        # Execute search
        try:
            self._results = search_entries(query=query, category=cat, days=days)
            print(f"DEBUG: search returned {len(self._results)} results")
        except Exception as e:
            print(f"DEBUG: search exception: {e}")
            self._results = []

        # Update results list
        self._results_listbox.delete(0, tk.END)
        for i, entry in enumerate(self._results):
            # Title first (most important), then category, then compact date
            title = entry['title'][:60]
            parts = [title]
            if entry.get("category"):
                parts.append(f"[{entry['category']}]")
            # Compact date: MM/DD or MM/DD/YY
            if entry.get('date'):
                date_parts = entry['date'].split('-')  # YYYY-MM-DD format
                if len(date_parts) == 3:
                    compact_date = f"{date_parts[1]}/{date_parts[2]}"
                    parts.append(compact_date)
            display = " · ".join(parts)
            self._results_listbox.insert(tk.END, display)
            # Alternating row colors for visual separation
            if i % 2 == 0:
                self._results_listbox.itemconfigure(i, bg="#FFFFFF")
            else:
                self._results_listbox.itemconfigure(i, bg="#F5F5F5")

        # Update count
        self._count_label.config(text=f"{len(self._results)} results")

        # Clear detail view
        self._clear_detail()

    def _open_chat(self) -> None:
        """Open the AI Chat window."""
        if self._on_chat:
            self._on_chat()

    def _chat_about_results(self) -> None:
        """Open AI Chat with only the current search results as context."""
        if not self._results:
            from tkinter import messagebox
            messagebox.showinfo(
                "No Results",
                "Run a search first to get results to chat about.",
                parent=self._root
            )
            return

        if not self._chat_window:
            from tkinter import messagebox
            messagebox.showerror(
                "Error",
                "Chat window not available.",
                parent=self._root
            )
            return

        # Build context description from current search
        query = self._search_var.get().strip() if self._search_var else ""
        category = self._category_var.get() if self._category_var else "All"
        context_desc = f"'{query}'" if query else "recent entries"
        if category != "All":
            context_desc += f" in {category}"

        # Open chat with these specific results
        self._chat_window.show_with_memories(self._results, context_desc)

    def _do_ai_summarize(self) -> None:
        """Summarize current search results using AI."""
        if not self._results:
            self._show_ai_result("No results to summarize. Run a search first.")
            return

        query = self._search_var.get().strip() or "all memories"

        # Show loading state
        self._ai_btn.config(state=tk.DISABLED, text="Thinking...")
        self._root.update()

        try:
            summary = summarize_search_results(query, self._results)
            self._show_ai_result(summary, title=f"AI Summary: {query}")
        except NoAPIKeyError:
            self._show_ai_result(
                "No API key configured.\n\n"
                "Add your Anthropic API key to config.json:\n"
                '  "ai_api_key": "sk-ant-..."'
            )
        except AIQueryError as e:
            self._show_ai_result(f"AI Error: {e}")
        finally:
            self._ai_btn.config(state=tk.NORMAL, text="AI Summarize")

    def _show_ai_result(self, text: str, title: str = "AI Summary") -> None:
        """Display AI result in the detail pane."""
        self._selected_entry = None
        self._meta_label.config(text=f"AI Generated | Based on {len(self._results)} entries")

        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert(tk.END, f"{title}\n")
        self._detail_text.insert(tk.END, "=" * len(title) + "\n\n")
        self._detail_text.insert(tk.END, text)
        self._detail_text.config(state=tk.DISABLED)

    def _on_select(self, event) -> None:
        """Handle selection in results list."""
        selection = self._results_listbox.curselection()
        if not selection:
            return

        # In multi-select mode, just update count, don't show detail
        if self._multi_select_var and self._multi_select_var.get():
            count = len(selection)
            self._count_label.config(text=f"{count} selected")
            return

        index = selection[0]
        if index < len(self._results):
            entry = self._results[index]
            self._show_detail(entry)

    def _on_double_click(self, event) -> None:
        """Handle double-click on results (could copy content, etc.)."""
        # For now, same as single click
        pass

    def _show_detail(self, entry: dict) -> None:
        """Show entry details in the detail pane."""
        self._selected_entry = entry

        # Update metadata label
        meta_parts = [f"ID: {entry['id']}", f"Date: {entry['date']}"]
        if entry.get("category"):
            meta_parts.append(f"Category: {entry['category']}")
        if entry.get("tags"):
            meta_parts.append(f"Tags: {entry['tags']}")
        if entry.get("session_id"):
            meta_parts.append(f"Session: {entry['session_id']}")
        if entry.get("pdf_path"):
            page_count = get_pdf_page_count(entry['pdf_path'])
            meta_parts.append(f"PDF: {page_count} pages")
        self._meta_label.config(text=" | ".join(meta_parts))

        # Show delete button
        self._delete_btn.grid()

        # Check if this is a PDF entry
        if entry.get("pdf_path") and is_pdf_support_available():
            self._show_pdf_viewer(entry)
        else:
            self._show_text_detail(entry)

    def _show_text_detail(self, entry: dict) -> None:
        """Show text content in the detail pane."""
        # Hide PDF viewer, show text
        self._pdf_frame.grid_remove()
        self._detail_text.grid(row=1, column=0, sticky="nsew")

        # Update detail text
        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert(tk.END, f"{entry['title']}\n")
        self._detail_text.insert(tk.END, "=" * len(entry["title"]) + "\n\n")
        self._detail_text.insert(tk.END, entry["content"])
        self._detail_text.config(state=tk.DISABLED)

    def _show_pdf_viewer(self, entry: dict) -> None:
        """Show PDF pages in the detail pane."""
        import os

        pdf_path = entry.get("pdf_path")
        if not pdf_path or not os.path.exists(pdf_path):
            # PDF file not found, fall back to text
            self._show_text_detail(entry)
            return

        # Hide text, show PDF viewer
        self._detail_text.grid_remove()
        self._pdf_frame.grid(row=1, column=0, sticky="nsew")

        # Clear previous PDF images
        for widget in self._pdf_inner_frame.winfo_children():
            widget.destroy()
        self._pdf_images.clear()

        # Render PDF pages
        try:
            images = render_all_pages(pdf_path, zoom=1.2)

            if not images:
                # No pages rendered, show text instead
                self._show_text_detail(entry)
                return

            # Convert PIL images to PhotoImage and display
            for i, pil_image in enumerate(images):
                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(pil_image)
                self._pdf_images.append(photo)  # Keep reference to prevent garbage collection

                # Create label to display the image
                page_label = ttk.Label(self._pdf_inner_frame, image=photo)
                page_label.pack(pady=5)

                # Add page number label
                page_num_label = ttk.Label(
                    self._pdf_inner_frame,
                    text=f"Page {i + 1} of {len(images)}",
                    font=("Segoe UI", 9),
                    foreground="gray"
                )
                page_num_label.pack(pady=(0, 10))

            # Scroll to top
            self._pdf_canvas.yview_moveto(0)

        except Exception as e:
            print(f"Error rendering PDF: {e}")
            self._show_text_detail(entry)

    def _clear_detail(self) -> None:
        """Clear the detail pane."""
        self._selected_entry = None
        self._meta_label.config(text="")
        self._delete_btn.grid_remove()  # Hide delete button

        # Clear text area
        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.config(state=tk.DISABLED)

        # Hide PDF viewer and clear images
        self._pdf_frame.grid_remove()
        for widget in self._pdf_inner_frame.winfo_children():
            widget.destroy()
        self._pdf_images.clear()

        # Show text area by default
        self._detail_text.grid(row=1, column=0, sticky="nsew")

    def _delete_selected(self) -> None:
        """Delete the currently selected entry after confirmation."""
        if not self._selected_entry:
            return

        entry_id = self._selected_entry['id']
        title = self._selected_entry['title'][:50]

        # Confirmation dialog
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "Delete Entry",
            f"Delete this entry?\n\n\"{title}...\"\n\nThis cannot be undone.",
            parent=self._root
        )

        if confirm:
            if delete_entry(entry_id):
                self._clear_detail()
                self._do_search()  # Refresh the list

    def _on_checkbox_canvas_resize(self, event):
        """Handle canvas resize to update checkbox frame width."""
        self._checkbox_canvas.itemconfig(self._checkbox_canvas_window, width=event.width)

    def _populate_checkboxes(self):
        """Populate the checkbox view with current results."""
        # Clear existing checkboxes
        for widget in self._checkbox_frame.winfo_children():
            widget.destroy()
        self._check_vars.clear()

        # Create checkbox for each result
        for i, entry in enumerate(self._results):
            var = tk.BooleanVar()
            self._check_vars[i] = var

            # Create frame for this row
            row_frame = ttk.Frame(self._checkbox_frame)
            row_frame.pack(fill=tk.X, padx=5, pady=2)

            # Checkbox
            cb = ttk.Checkbutton(row_frame, variable=var)
            cb.pack(side=tk.LEFT)

            # Entry label - clickable to view
            title = entry.get('title', 'Untitled')
            date = entry.get('created_at', '')[:10] if entry.get('created_at') else ''
            display = f"{title}"
            if date:
                display += f" ({date})"

            label = tk.Label(
                row_frame,
                text=display,
                font=("Segoe UI", 10),
                anchor="w",
                cursor="hand2",
                bg="#FFFFFF" if i % 2 == 0 else "#F5F5F5"
            )
            label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

            # Click label to view details
            label.bind("<Button-1>", lambda e, idx=i: self._on_checkbox_label_click(idx))

            # Alternate row colors
            row_frame.configure(style="" if i % 2 == 0 else "Alt.TFrame")

    def _on_checkbox_label_click(self, index):
        """Handle click on checkbox label to view entry."""
        if 0 <= index < len(self._results):
            self._selected_entry = self._results[index]
            self._display_detail(self._selected_entry)

    def _get_checked_indices(self):
        """Get list of checked item indices."""
        return [i for i, var in self._check_vars.items() if var.get()]

    def _toggle_multi_select(self) -> None:
        """Toggle between single and multi-select mode."""
        if self._multi_select_var.get():
            # Enable multi-select
            self._delete_selected_btn.pack(side=tk.LEFT)
            self._remove_duplicates_btn.pack(side=tk.LEFT, padx=(5, 0))
            # Hide the single-entry delete button
            self._delete_btn.grid_remove()
            self._clear_detail()
            # Show multi-select notice
            self._multi_select_notice.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
            self._detail_text.grid_remove()

            # Switch from listbox to checkbox view
            self._results_listbox.grid_remove()
            self._listbox_scrollbar.grid_remove()

            self._checkbox_canvas.grid(row=0, column=0, sticky="nsew")
            self._checkbox_scrollbar.grid(row=0, column=1, sticky="ns")

            # Populate checkboxes with current results
            self._populate_checkboxes()
        else:
            # Disable multi-select
            self._delete_selected_btn.pack_forget()
            self._remove_duplicates_btn.pack_forget()
            # Hide multi-select notice
            self._multi_select_notice.grid_remove()
            self._detail_text.grid(row=1, column=0, sticky="nsew")

            # Switch back to listbox view
            self._checkbox_canvas.grid_remove()
            self._checkbox_scrollbar.grid_remove()

            self._results_listbox.grid(row=0, column=0, sticky="nsew")
            self._listbox_scrollbar.grid(row=0, column=1, sticky="ns")

            # Clear selection
            self._results_listbox.selection_clear(0, tk.END)

    def _delete_multiple(self) -> None:
        """Delete all selected entries after confirmation."""
        # Get checked items
        checked_indices = self._get_checked_indices()
        if not checked_indices:
            from tkinter import messagebox
            messagebox.showinfo(
                "No Selection",
                "Please check at least one entry to delete.",
                parent=self._root
            )
            return

        # Get selected entries
        selected_entries = [self._results[i] for i in checked_indices]
        count = len(selected_entries)

        # Confirmation dialog
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "Delete Entries",
            f"Delete {count} selected entries?\n\nThis cannot be undone.",
            parent=self._root
        )

        if confirm:
            deleted = 0
            for entry in selected_entries:
                if delete_entry(entry['id']):
                    deleted += 1

            # Refresh the list
            self._do_search()

            # Show result
            if deleted == count:
                messagebox.showinfo("Deleted", f"Deleted {deleted} entries.", parent=self._root)
            else:
                messagebox.showwarning(
                    "Partial Delete",
                    f"Deleted {deleted} of {count} entries.",
                    parent=self._root
                )

    def _remove_duplicates(self) -> None:
        """Merge selected entries into one clean entry and delete duplicates."""
        # Get checked items
        checked_indices = self._get_checked_indices()
        if len(checked_indices) < 2:
            from tkinter import messagebox
            messagebox.showinfo(
                "Select Multiple",
                "Please check at least 2 entries to remove duplicates.",
                parent=self._root
            )
            return

        # Get selected entries sorted by date (oldest first)
        selected_entries = [self._results[i] for i in checked_indices]
        selected_entries.sort(key=lambda e: e.get('created_at', ''))

        # Confirmation dialog
        from tkinter import messagebox
        confirm = messagebox.askyesno(
            "Remove Duplicates",
            f"Merge {len(selected_entries)} entries into one clean entry?\n\n"
            f"This will:\n"
            f"1. Extract unique content from all selected entries\n"
            f"2. Create a new merged entry\n"
            f"3. Delete the {len(selected_entries)} selected entries\n\n"
            f"This cannot be undone.",
            parent=self._root
        )

        if not confirm:
            return

        # Merge content - remove duplicates by splitting into lines
        all_content = []
        for entry in selected_entries:
            content = entry.get('content', '').strip()
            if content:
                all_content.append(content)

        # Deduplicate by lines
        seen_lines = set()
        unique_lines = []
        for content_block in all_content:
            for line in content_block.split('\n'):
                line_stripped = line.strip()
                if line_stripped and line_stripped not in seen_lines:
                    seen_lines.add(line_stripped)
                    unique_lines.append(line)

        merged_content = '\n'.join(unique_lines)

        # Use the first entry's title (or create a new one)
        first_entry = selected_entries[0]
        merged_title = first_entry.get('title', 'Merged Entry')
        if not merged_title.startswith('[Merged]'):
            merged_title = f"[Merged] {merged_title}"

        # Use the first entry's category and tags
        category = first_entry.get('category', 'note')
        tags = first_entry.get('tags', '')
        if tags and 'merged' not in tags:
            tags = f"{tags}, merged"
        else:
            tags = 'merged'

        # Create new merged entry
        from claude_memory.database import add_entry
        new_entry_id = add_entry(
            title=merged_title,
            content=merged_content,
            category=category,
            tags=tags
        )

        if not new_entry_id:
            messagebox.showerror(
                "Error",
                "Failed to create merged entry.",
                parent=self._root
            )
            return

        # Delete old entries
        deleted = 0
        for entry in selected_entries:
            if delete_entry(entry['id']):
                deleted += 1

        # Refresh and show result
        self._do_search()

        messagebox.showinfo(
            "Success",
            f"Created merged entry with {len(unique_lines)} unique lines.\n"
            f"Deleted {deleted} duplicate entries.",
            parent=self._root
        )

    def _on_ctrl_v(self, event) -> None:
        """Handle Ctrl+V - show quick add dialog with clipboard content."""
        # Check if focus is in search entry - if so, let normal paste work
        focused = self._root.focus_get()
        if focused and isinstance(focused, ttk.Entry):
            return  # Let normal paste happen

        self._show_quick_add()
        return "break"  # Prevent default handling

    def _show_quick_add(self) -> None:
        """Show the quick add dialog to paste/type a new memory."""
        dialog = tk.Toplevel(self._root)
        dialog.title("Quick Add Memory")
        dialog.geometry("500x400")
        dialog.transient(self._root)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self._root.winfo_x() + (self._root.winfo_width() - 500) // 2
        y = self._root.winfo_y() + (self._root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")

        # Title input
        title_frame = ttk.Frame(dialog, padding="10 10 10 5")
        title_frame.pack(fill=tk.X)
        ttk.Label(title_frame, text="Title:").pack(side=tk.LEFT)
        title_var = tk.StringVar()
        title_entry = ttk.Entry(title_frame, textvariable=title_var, font=("Segoe UI", 11))
        title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        # Category input
        cat_frame = ttk.Frame(dialog, padding="10 5 10 5")
        cat_frame.pack(fill=tk.X)
        ttk.Label(cat_frame, text="Category:").pack(side=tk.LEFT)
        cat_var = tk.StringVar(value="note")
        cat_entry = ttk.Combobox(
            cat_frame,
            textvariable=cat_var,
            values=["note", "reference", "idea", "snippet", "email", "conversation"],
            width=15
        )
        cat_entry.pack(side=tk.LEFT, padx=(10, 0))

        # Content area
        content_frame = ttk.Frame(dialog, padding="10 5 10 5")
        content_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(content_frame, text="Content (paste with Ctrl+V):").pack(anchor=tk.W)
        content_text = scrolledtext.ScrolledText(
            content_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            height=12
        )
        content_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Try to paste clipboard content automatically
        try:
            clipboard = self._root.clipboard_get()
            if clipboard:
                content_text.insert("1.0", clipboard)
                # Auto-generate title from first line if not set
                first_line = clipboard.split('\n')[0][:60]
                if first_line:
                    title_var.set(first_line)
        except tk.TclError:
            pass  # No clipboard content

        # Buttons
        btn_frame = ttk.Frame(dialog, padding="10")
        btn_frame.pack(fill=tk.X)

        def save_and_close():
            title = title_var.get().strip()
            content = content_text.get("1.0", tk.END).strip()
            category = cat_var.get().strip() or "note"

            if not title:
                title = "Untitled note"
            if not content:
                from tkinter import messagebox
                messagebox.showwarning("Empty Content", "Please enter some content.", parent=dialog)
                return

            # Save to database
            entry_id = add_entry(
                title=title,
                content=content,
                category=category,
                tags="quick-add"
            )

            dialog.destroy()
            self._refresh()  # Refresh the list

        ttk.Button(btn_frame, text="Save", command=save_and_close).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        # Focus title and bind Enter to save
        title_entry.focus()
        dialog.bind("<Control-Return>", lambda e: save_and_close())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def _import_pdf(self) -> None:
        """Import a PDF file and create a memory entry for it."""
        if not is_pdf_support_available():
            from tkinter import messagebox
            messagebox.showerror(
                "PDF Support Not Available",
                "PDF support requires PyMuPDF and Pillow.\n\n"
                "Install with: pip install PyMuPDF Pillow",
                parent=self._root
            )
            return

        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Import PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            parent=self._root
        )

        if not file_path:
            return  # User cancelled

        # Show progress dialog
        progress = tk.Toplevel(self._root)
        progress.title("Importing PDF...")
        progress.geometry("300x80")
        progress.transient(self._root)
        progress.grab_set()

        # Center on parent
        progress.update_idletasks()
        x = self._root.winfo_x() + (self._root.winfo_width() - 300) // 2
        y = self._root.winfo_y() + (self._root.winfo_height() - 80) // 2
        progress.geometry(f"+{x}+{y}")

        ttk.Label(progress, text="Importing PDF and extracting text...", padding=20).pack()
        progress.update()

        try:
            # Import the PDF
            stored_path, extracted_text, title = import_pdf(file_path)

            progress.destroy()

            if stored_path is None:
                from tkinter import messagebox
                messagebox.showerror("Import Failed", title, parent=self._root)  # title contains error message
                return

            # Show dialog to customize title/category before saving
            self._show_pdf_save_dialog(stored_path, extracted_text, title)

        except Exception as e:
            progress.destroy()
            from tkinter import messagebox
            messagebox.showerror("Import Error", f"Failed to import PDF:\n{e}", parent=self._root)

    def _show_pdf_save_dialog(self, pdf_path: str, extracted_text: str, default_title: str) -> None:
        """Show dialog to customize PDF entry before saving."""
        dialog = tk.Toplevel(self._root)
        dialog.title("Save PDF")
        dialog.geometry("500x300")
        dialog.transient(self._root)
        dialog.grab_set()

        # Center on parent
        dialog.update_idletasks()
        x = self._root.winfo_x() + (self._root.winfo_width() - 500) // 2
        y = self._root.winfo_y() + (self._root.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")

        # Title input
        title_frame = ttk.Frame(dialog, padding="10 10 10 5")
        title_frame.pack(fill=tk.X)
        ttk.Label(title_frame, text="Title:").pack(side=tk.LEFT)
        title_var = tk.StringVar(value=default_title)
        title_entry = ttk.Entry(title_frame, textvariable=title_var, font=("Segoe UI", 11))
        title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))

        # Category input
        cat_frame = ttk.Frame(dialog, padding="10 5 10 5")
        cat_frame.pack(fill=tk.X)
        ttk.Label(cat_frame, text="Category:").pack(side=tk.LEFT)
        cat_var = tk.StringVar(value="document")
        cat_entry = ttk.Combobox(
            cat_frame,
            textvariable=cat_var,
            values=["document", "reference", "research", "manual", "report"],
            width=15
        )
        cat_entry.pack(side=tk.LEFT, padx=(10, 0))

        # Tags input
        tags_frame = ttk.Frame(dialog, padding="10 5 10 5")
        tags_frame.pack(fill=tk.X)
        ttk.Label(tags_frame, text="Tags:").pack(side=tk.LEFT)
        tags_var = tk.StringVar(value="pdf")
        tags_entry = ttk.Entry(tags_frame, textvariable=tags_var, width=30)
        tags_entry.pack(side=tk.LEFT, padx=(10, 0))

        # Preview of extracted text
        preview_frame = ttk.LabelFrame(dialog, text="Extracted Text Preview", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        preview_text = scrolledtext.ScrolledText(
            preview_frame,
            font=("Consolas", 9),
            wrap=tk.WORD,
            height=8,
            state=tk.NORMAL
        )
        preview_text.pack(fill=tk.BOTH, expand=True)
        preview_text.insert("1.0", extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))
        preview_text.config(state=tk.DISABLED)

        # Buttons
        btn_frame = ttk.Frame(dialog, padding="10")
        btn_frame.pack(fill=tk.X)

        def save_and_close():
            title = title_var.get().strip() or default_title
            category = cat_var.get().strip() or "document"
            tags = tags_var.get().strip() or "pdf"

            # Save to database with PDF path
            entry_id = add_entry(
                title=title,
                content=extracted_text,
                category=category,
                tags=tags,
                pdf_path=pdf_path
            )

            dialog.destroy()
            self._refresh()  # Refresh the list

            from tkinter import messagebox
            messagebox.showinfo(
                "PDF Imported",
                f"PDF saved as entry #{entry_id}\n\nClick on it to view the formatted PDF.",
                parent=self._root
            )

        ttk.Button(btn_frame, text="Save", command=save_and_close).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        # Focus title
        title_entry.focus()
        title_entry.select_range(0, tk.END)
        dialog.bind("<Return>", lambda e: save_and_close())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def show(self) -> None:
        """Show the search window."""
        if self._root is None:
            self._create_window()

        # Initialize last entry ID for auto-refresh
        try:
            recent = get_recent_entries(limit=1)
            if recent:
                self._last_entry_id = recent[0]['id']
        except Exception:
            pass

        self._refresh_categories()
        self._do_search()  # Refresh results

        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()

        # Start auto-refresh
        self._start_auto_refresh()

        # Focus search box
        for widget in self._root.winfo_children():
            if isinstance(widget, ttk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Entry):
                        child.focus()
                        child.select_range(0, tk.END)
                        break
                break

    def hide(self) -> None:
        """Hide the search window."""
        self._stop_auto_refresh()
        if self._root:
            self._root.withdraw()

    def show_entry(self, entry_id: int) -> None:
        """Show a specific entry by ID."""
        entry = get_entry_by_id(entry_id)
        if entry:
            self.show()
            self._show_detail(entry)

    def toggle(self) -> None:
        """Toggle window visibility."""
        if self._root is None or not self._root.winfo_viewable():
            self.show()
        else:
            self.hide()

    def mainloop(self) -> None:
        """Run the tkinter main loop."""
        if self._root:
            self._root.mainloop()

    def destroy(self) -> None:
        """Destroy the window."""
        if self._root:
            self._root.destroy()
            self._root = None
