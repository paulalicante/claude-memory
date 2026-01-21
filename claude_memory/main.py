"""
Main entry point for Claude Memory app.
Wires together all components: tray, clipboard watcher, search window, hotkeys.
"""

import sys
import threading
import tkinter as tk
from typing import Optional

import keyboard
import pyperclip
from tkinter import ttk, scrolledtext

from . import constants
from .config import Config
from .database import init_database, backup_database, get_statistics, add_entry, get_categories
from .clipboard_watcher import ClipboardWatcher
from .tray import TrayApp
from .search_window import SearchWindow
from .chat_window import ChatWindow
from .notifications import notify_saved
from . import http_server


class ClipboardSaveDialog:
    """Dialog for saving clipboard content to memory."""

    def __init__(self, parent: tk.Tk, clipboard_content: str, on_saved: Optional[callable] = None):
        self._clipboard_content = clipboard_content
        self._on_saved = on_saved
        self._result = None

        # Create dialog window
        self._dialog = tk.Toplevel(parent)
        self._dialog.title("Save Clipboard to Memory")
        self._dialog.geometry("500x450")
        self._dialog.transient(parent)
        self._dialog.grab_set()

        # Make it appear in center
        self._dialog.update_idletasks()
        x = (self._dialog.winfo_screenwidth() - 500) // 2
        y = (self._dialog.winfo_screenheight() - 450) // 2
        self._dialog.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self._dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title field
        ttk.Label(main_frame, text="Title:").pack(anchor="w")
        self._title_var = tk.StringVar()
        title_entry = ttk.Entry(main_frame, textvariable=self._title_var, font=("Segoe UI", 11))
        title_entry.pack(fill="x", pady=(0, 10))
        title_entry.focus()

        # Category dropdown
        ttk.Label(main_frame, text="Category (optional):").pack(anchor="w")
        self._category_var = tk.StringVar()
        category_combo = ttk.Combobox(main_frame, textvariable=self._category_var)
        try:
            categories = get_categories()
            category_combo["values"] = [""] + categories
        except Exception:
            pass
        category_combo.pack(fill="x", pady=(0, 10))

        # Tags field
        ttk.Label(main_frame, text="Tags (optional, comma-separated):").pack(anchor="w")
        self._tags_var = tk.StringVar()
        tags_entry = ttk.Entry(main_frame, textvariable=self._tags_var)
        tags_entry.pack(fill="x", pady=(0, 10))

        # Clipboard content preview
        ttk.Label(main_frame, text="Content Preview:").pack(anchor="w")
        preview = scrolledtext.ScrolledText(main_frame, height=12, font=("Consolas", 9), state=tk.NORMAL)
        preview.insert("1.0", self._clipboard_content[:2000] + ("..." if len(self._clipboard_content) > 2000 else ""))
        preview.config(state=tk.DISABLED)
        preview.pack(fill="both", expand=True, pady=(0, 10))

        # Content length info
        ttk.Label(main_frame, text=f"Content length: {len(self._clipboard_content)} characters").pack(anchor="w", pady=(0, 10))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="right", padx=(5, 0))
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right")

        # Bind Enter to save
        self._dialog.bind("<Return>", lambda e: self._on_save())
        self._dialog.bind("<Escape>", lambda e: self._on_cancel())

    def _on_save(self):
        """Handle save button click."""
        title = self._title_var.get().strip()
        if not title:
            from tkinter import messagebox
            messagebox.showwarning("Title Required", "Please enter a title.", parent=self._dialog)
            return

        category = self._category_var.get().strip() or None
        tags = self._tags_var.get().strip() or None

        try:
            entry_id = add_entry(
                title=title,
                content=self._clipboard_content,
                category=category,
                tags=tags,
            )
            notify_saved(title)
            if self._on_saved:
                self._on_saved({"id": entry_id, "title": title})
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to save: {e}", parent=self._dialog)
            return

        self._dialog.destroy()

    def _on_cancel(self):
        """Handle cancel button click."""
        self._dialog.destroy()


class ClaudeMemoryApp:
    """
    Main application class that coordinates all components.
    """

    def __init__(self):
        self._config = Config()
        self._watcher: Optional[ClipboardWatcher] = None
        self._tray: Optional[TrayApp] = None
        self._search_window: Optional[SearchWindow] = None
        self._chat_window: Optional[ChatWindow] = None
        self._running = False
        self._root: Optional[tk.Tk] = None

    def _setup_database(self) -> None:
        """Initialize and backup the database."""
        init_database()
        backup_database()

    def _setup_http_server(self) -> None:
        """Start the HTTP server if enabled."""
        if self._config.http_server_enabled:
            try:
                port = self._config.http_server_port
                http_server.start_server(port=port)
                print(f"HTTP server started on http://127.0.0.1:{port}")
            except Exception as e:
                print(f"Warning: Could not start HTTP server: {e}")

    def _setup_hotkey(self) -> None:
        """Register global hotkey for search window."""
        try:
            keyboard.add_hotkey(
                self._config.hotkey,
                self._on_hotkey,
                suppress=True,
            )
        except Exception as e:
            print(f"Warning: Could not register hotkey: {e}")

    def _on_hotkey(self) -> None:
        """Handle global hotkey press."""
        if self._search_window and self._root:
            # Schedule on tkinter's thread
            self._root.after(0, self._search_window.show)

    def _on_entry_saved(self, entry: dict) -> None:
        """Callback when an entry is saved."""
        # Update tray tooltip with new count
        if self._tray:
            try:
                stats = get_statistics()
                self._tray.update_tooltip(stats["total"])
            except Exception:
                pass

    def _on_search_clicked(self) -> None:
        """Callback when Search is clicked in tray menu."""
        if self._search_window and self._root:
            self._root.after(0, self._search_window.show)

    def _on_chat_clicked(self) -> None:
        """Callback when AI Chat is clicked in tray menu."""
        if self._chat_window and self._root:
            self._root.after(0, self._chat_window.show)

    def _on_entry_clicked(self, entry_id: int) -> None:
        """Callback when an entry is clicked in tray menu."""
        if self._search_window and self._root:
            self._root.after(0, lambda: self._search_window.show_entry(entry_id))

    def _on_save_clipboard_clicked(self) -> None:
        """Callback when Save Clipboard is clicked in tray menu."""
        if self._root:
            self._root.after(0, self._show_clipboard_save_dialog)

    def _show_clipboard_save_dialog(self) -> None:
        """Show the clipboard save dialog."""
        try:
            clipboard_content = pyperclip.paste()
            if not clipboard_content or not clipboard_content.strip():
                from tkinter import messagebox
                messagebox.showinfo("Empty Clipboard", "Clipboard is empty.", parent=self._root)
                return

            ClipboardSaveDialog(self._root, clipboard_content, on_saved=self._on_entry_saved)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Could not read clipboard: {e}", parent=self._root)

    def _on_quit(self) -> None:
        """Callback when Quit is clicked."""
        self._running = False
        if self._watcher:
            self._watcher.stop()
        http_server.stop_server()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self._root:
            self._root.after(0, self._root.quit)

    def _run_tray(self) -> None:
        """Run the tray app in a separate thread."""
        self._tray = TrayApp(
            on_search=self._on_search_clicked,
            on_chat=self._on_chat_clicked,
            on_quit=self._on_quit,
            on_entry_click=self._on_entry_clicked,
            on_save_clipboard=self._on_save_clipboard_clicked,
        )
        self._tray.run()

    def run(self) -> None:
        """Run the application."""
        self._running = True

        # Initialize database
        self._setup_database()

        # Start HTTP server for external integrations
        self._setup_http_server()

        # Create hidden root window for tkinter event loop
        self._root = tk.Tk()
        self._root.withdraw()  # Hide the root window

        # Create chat window first (search window needs reference to it)
        self._chat_window = ChatWindow()

        # Create search window with callback to open chat and reference to chat window
        self._search_window = SearchWindow(
            on_chat=self._on_chat_clicked,
            chat_window=self._chat_window
        )

        # Setup global hotkey
        self._setup_hotkey()

        # Start clipboard watcher
        self._watcher = ClipboardWatcher(on_save=self._on_entry_saved)
        self._watcher.start()

        # Run tray in separate thread
        tray_thread = threading.Thread(target=self._run_tray, daemon=True)
        tray_thread.start()

        # Run tkinter mainloop in main thread
        self._root.mainloop()

        # Cleanup
        if self._tray:
            self._tray.stop()


def main():
    """Main entry point."""
    app = ClaudeMemoryApp()
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
