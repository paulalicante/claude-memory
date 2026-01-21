"""
Search window UI for Claude Memory app.
Built with tkinter for lightweight, no-dependency UI.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional

from . import constants
from .database import search_entries, get_categories, get_entry_by_id, get_recent_entries, delete_entry, add_entry
from .ai_query import summarize_search_results, NoAPIKeyError, AIQueryError


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

        scrollbar = ttk.Scrollbar(
            left_frame, orient=tk.VERTICAL, command=self._results_listbox.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._results_listbox.config(yscrollcommand=scrollbar.set)

        self._results_listbox.bind("<<ListboxSelect>>", self._on_select)
        self._results_listbox.bind("<Double-Button-1>", self._on_double_click)

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

        # Detail text area
        self._detail_text = scrolledtext.ScrolledText(
            right_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
        )
        self._detail_text.grid(row=1, column=0, sticky="nsew")

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
        if not self._root or not self._root.winfo_viewable():
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
        self._meta_label.config(text=" | ".join(meta_parts))

        # Show delete button
        self._delete_btn.grid()

        # Update detail text
        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert(tk.END, f"{entry['title']}\n")
        self._detail_text.insert(tk.END, "=" * len(entry["title"]) + "\n\n")
        self._detail_text.insert(tk.END, entry["content"])
        self._detail_text.config(state=tk.DISABLED)

    def _clear_detail(self) -> None:
        """Clear the detail pane."""
        self._selected_entry = None
        self._meta_label.config(text="")
        self._delete_btn.grid_remove()  # Hide delete button
        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.config(state=tk.DISABLED)

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
