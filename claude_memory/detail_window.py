"""
Detail window for viewing memory entries.
Shows the full content of a selected memory in a separate window.
"""

import tkinter as tk
from typing import Optional, List
import json
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from . import constants


class DetailWindow:
    """Separate window for viewing memory entry details."""

    def __init__(self):
        """Initialize the detail window (hidden by default)."""
        self._window: Optional[tk.Toplevel] = None
        self._current_entry: Optional[dict] = None

        # UI elements
        self._meta_label: Optional[ttk.Label] = None
        self._delete_btn: Optional[ttk.Button] = None
        self._detail_text: Optional[tk.Text] = None

        # PDF viewer
        self._pdf_frame: Optional[tk.Frame] = None
        self._pdf_canvas: Optional[tk.Canvas] = None
        self._pdf_inner_frame: Optional[tk.Frame] = None
        self._pdf_images: List = []

        # HTML viewer
        self._html_frame: Optional[tk.Frame] = None
        self._html_viewer = None
        self._html_text: Optional[tk.Text] = None
        self._use_tkinterweb: bool = False

        # Callback for delete
        self._on_delete_callback = None

    def show(self, entry: dict, on_delete_callback=None) -> None:
        """Show the detail window with the given entry."""
        self._current_entry = entry
        self._on_delete_callback = on_delete_callback

        if self._window is None:
            self._create_window()

        self._display_entry(entry)
        self._window.deiconify()
        self._window.lift()

    def hide(self) -> None:
        """Hide the detail window."""
        if self._window:
            self._window.withdraw()

    def destroy(self) -> None:
        """Destroy the detail window."""
        if self._window:
            self._window.destroy()
            self._window = None

    def _create_window(self) -> None:
        """Create the detail window."""
        self._window = tk.Toplevel()
        self._window.title(f"{constants.APP_NAME} - Detail")
        self._window.geometry("700x600")

        # Handle window close - hide instead of destroy
        self._window.protocol("WM_DELETE_WINDOW", self.hide)

        # Configure grid weights
        self._window.columnconfigure(0, weight=1)
        self._window.rowconfigure(1, weight=1)

        # Header with metadata and delete button
        header_frame = ttk.Frame(self._window, padding="10 10 10 5")
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)

        self._meta_label = ttk.Label(
            header_frame, text="", font=("Segoe UI", 9), foreground="gray"
        )
        self._meta_label.grid(row=0, column=0, sticky="w")

        self._delete_btn = ttk.Button(
            header_frame, text="Delete", command=self._delete_current, bootstyle="danger"
        )
        self._delete_btn.grid(row=0, column=1, sticky="e", padx=(10, 0))

        # Main content area
        content_frame = ttk.Frame(self._window, padding="10 5 10 10")
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(0, weight=1)

        # Text viewer (default)
        self._detail_text = tk.Text(
            content_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            padx=10,
            pady=10,
            state=tk.DISABLED,
        )
        text_scrollbar = ttk.Scrollbar(
            content_frame, orient=tk.VERTICAL, command=self._detail_text.yview
        )
        self._detail_text.configure(yscrollcommand=text_scrollbar.set)
        self._detail_text.grid(row=0, column=0, sticky="nsew")
        text_scrollbar.grid(row=0, column=1, sticky="ns")

        # PDF viewer (hidden by default)
        self._create_pdf_viewer(content_frame)

        # HTML viewer (hidden by default)
        self._create_html_viewer(content_frame)

    def _create_pdf_viewer(self, parent: tk.Frame) -> None:
        """Create the PDF viewer frame."""
        self._pdf_frame = ttk.Frame(parent)

        # Create canvas with scrollbar
        self._pdf_canvas = tk.Canvas(self._pdf_frame, bg="white")
        pdf_scrollbar = ttk.Scrollbar(
            self._pdf_frame, orient=tk.VERTICAL, command=self._pdf_canvas.yview
        )
        self._pdf_canvas.configure(yscrollcommand=pdf_scrollbar.set)

        self._pdf_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pdf_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Inner frame to hold PDF images
        self._pdf_inner_frame = ttk.Frame(self._pdf_canvas)
        self._pdf_canvas_window = self._pdf_canvas.create_window(
            (0, 0), window=self._pdf_inner_frame, anchor="nw"
        )

        # Configure scrolling
        def _configure_scroll(event):
            self._pdf_canvas.configure(scrollregion=self._pdf_canvas.bbox("all"))

        self._pdf_inner_frame.bind("<Configure>", _configure_scroll)

        def _configure_canvas(event):
            self._pdf_canvas.itemconfig(self._pdf_canvas_window, width=event.width)

        self._pdf_canvas.bind("<Configure>", _configure_canvas)

    def _create_html_viewer(self, parent: tk.Frame) -> None:
        """Create the HTML viewer frame."""
        self._html_frame = ttk.Frame(parent)

        # Try to use tkinterweb for proper HTML rendering
        try:
            from tkinterweb import HtmlFrame
            self._html_viewer = HtmlFrame(self._html_frame, messages_enabled=False)
            self._html_viewer.pack(fill=tk.BOTH, expand=True)
            self._use_tkinterweb = True
        except ImportError:
            # Fallback to basic text widget
            self._html_text = tk.Text(
                self._html_frame,
                wrap=tk.WORD,
                font=("Segoe UI", 10),
                padx=10,
                pady=10,
                state=tk.DISABLED
            )
            html_scrollbar = ttk.Scrollbar(
                self._html_frame, orient=tk.VERTICAL, command=self._html_text.yview
            )
            self._html_text.configure(yscrollcommand=html_scrollbar.set)
            self._html_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            html_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self._use_tkinterweb = False

    def _display_entry(self, entry: dict) -> None:
        """Display the entry content in the appropriate viewer."""
        # Update window title
        self._window.title(f"{constants.APP_NAME} - {entry.get('title', 'Detail')}")

        # Update metadata
        category = entry.get("category", "None")
        tags = entry.get("tags", "")
        date = entry.get("created_date", "Unknown")
        self._meta_label.config(
            text=f"Category: {category} | Tags: {tags} | Created: {date}"
        )

        # Check if this is a PDF entry
        if self._is_pdf_entry(entry):
            self._show_pdf_viewer(entry)
        # Check if this is an HTML email
        elif self._is_html_entry(entry):
            self._show_html_viewer(entry)
        else:
            self._show_text_detail(entry)

    def _is_pdf_entry(self, entry: dict) -> bool:
        """Check if entry has PDF data."""
        try:
            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            return metadata.get("content_type") == "pdf"
        except:
            return False

    def _is_html_entry(self, entry: dict) -> bool:
        """Check if entry has HTML email data."""
        try:
            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            return metadata.get("content_type") == "html" and "html_content" in metadata
        except:
            return False

    def _show_text_detail(self, entry: dict) -> None:
        """Show text content in the detail pane."""
        # Hide other viewers
        self._pdf_frame.pack_forget()
        self._html_frame.pack_forget()

        # Show text viewer
        self._detail_text.grid(row=0, column=0, sticky="nsew")

        # Update text
        self._detail_text.config(state=tk.NORMAL)
        self._detail_text.delete("1.0", tk.END)
        self._detail_text.insert(tk.END, entry.get("content", ""))
        self._detail_text.config(state=tk.DISABLED)

    def _show_pdf_viewer(self, entry: dict) -> None:
        """Show PDF content in the detail pane."""
        from .pdf_handler import is_pdf_support_available, render_pdf_to_images
        from PIL import ImageTk

        if not is_pdf_support_available():
            self._show_text_detail(entry)
            return

        try:
            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            pdf_filename = metadata.get("pdf_filename")

            if not pdf_filename:
                self._show_text_detail(entry)
                return

            # Hide other viewers
            self._detail_text.grid_remove()
            self._html_frame.pack_forget()

            # Show PDF viewer
            self._pdf_frame.grid(row=0, column=0, sticky="nsew")

            # Clear previous images
            for widget in self._pdf_inner_frame.winfo_children():
                widget.destroy()
            self._pdf_images.clear()

            # Render PDF pages
            import os
            pdf_path = os.path.join("pdfs", pdf_filename)

            if os.path.exists(pdf_path):
                page_images = render_pdf_to_images(pdf_path, max_width=650)

                for i, pil_image in enumerate(page_images):
                    photo = ImageTk.PhotoImage(pil_image)
                    self._pdf_images.append(photo)

                    label = tk.Label(self._pdf_inner_frame, image=photo, bg="white")
                    label.pack(pady=5)

                    if i < len(page_images) - 1:
                        sep = ttk.Separator(self._pdf_inner_frame, orient=tk.HORIZONTAL)
                        sep.pack(fill=tk.X, pady=10)

        except Exception as e:
            print(f"Error showing PDF: {e}")
            self._show_text_detail(entry)

    def _show_html_viewer(self, entry: dict) -> None:
        """Show HTML email content in the detail pane."""
        try:
            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            html_content = metadata.get("html_content", "")

            if not html_content:
                self._show_text_detail(entry)
                return

            # Hide other viewers
            self._detail_text.grid_remove()
            self._pdf_frame.pack_forget()

            # Show HTML viewer
            self._html_frame.grid(row=0, column=0, sticky="nsew")

            if self._use_tkinterweb:
                sender = metadata.get('sender', 'Unknown')
                subject = metadata.get('subject', 'No subject')

                full_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{
                            font-family: 'Segoe UI', Arial, sans-serif;
                            margin: 15px;
                            background: white;
                        }}
                        .email-header {{
                            background: #f5f5f5;
                            padding: 15px;
                            border-radius: 5px;
                            margin-bottom: 20px;
                            border-left: 4px solid #4A90E2;
                        }}
                        .email-header h3 {{
                            margin: 0 0 10px 0;
                            color: #333;
                        }}
                        .email-header p {{
                            margin: 5px 0;
                            color: #666;
                        }}
                        .email-body {{
                            line-height: 1.6;
                        }}
                    </style>
                </head>
                <body>
                    <div class="email-header">
                        <h3>{entry.get('title', 'Email')}</h3>
                        <p><strong>From:</strong> {sender}</p>
                        <p><strong>Subject:</strong> {subject}</p>
                    </div>
                    <div class="email-body">
                        {html_content}
                    </div>
                </body>
                </html>
                """

                self._html_viewer.load_html(full_html)
            else:
                self._show_text_detail(entry)

        except Exception as e:
            print(f"Error rendering HTML: {e}")
            self._show_text_detail(entry)

    def _delete_current(self) -> None:
        """Delete the currently displayed entry."""
        if self._current_entry and self._on_delete_callback:
            self._on_delete_callback(self._current_entry)
            self.hide()
