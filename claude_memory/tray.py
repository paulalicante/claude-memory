"""
System tray functionality for Claude Memory app.
"""

import os
import subprocess
import sys
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from . import constants
from .config import Config, get_app_dir, get_config_path
from .database import get_statistics, get_recent_entries, get_categories


def create_placeholder_icon(size: int = 64) -> Image.Image:
    """Create a simple placeholder icon (a brain-like shape)."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw a simple database/memory chip icon
    padding = size // 8
    width = size - 2 * padding
    height = size - 2 * padding

    # Main rectangle (chip body)
    draw.rounded_rectangle(
        [padding, padding, padding + width, padding + height],
        radius=size // 10,
        fill=(70, 130, 180),  # Steel blue
        outline=(50, 100, 150),
        width=2,
    )

    # Inner details (circuit-like lines)
    cx = size // 2
    cy = size // 2
    line_color = (200, 220, 240)

    # Horizontal lines
    for y_offset in [-height // 6, 0, height // 6]:
        y = cy + y_offset
        draw.line(
            [padding + width // 4, y, padding + 3 * width // 4, y],
            fill=line_color,
            width=2,
        )

    # Small dots at intersections
    dot_radius = size // 20
    for y_offset in [-height // 6, 0, height // 6]:
        for x_offset in [-width // 4, 0, width // 4]:
            x = cx + x_offset
            y = cy + y_offset
            draw.ellipse(
                [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
                fill=(255, 255, 255),
            )

    return image


class TrayApp:
    """
    System tray application.
    Provides menu for accessing search, recent entries, and settings.
    """

    def __init__(
        self,
        on_search: Optional[Callable] = None,
        on_chat: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        on_entry_click: Optional[Callable[[int], None]] = None,
        on_save_clipboard: Optional[Callable] = None,
    ):
        """
        Initialize the tray app.

        Args:
            on_search: Callback when Search is clicked
            on_chat: Callback when AI Chat is clicked
            on_quit: Callback when Quit is clicked
            on_entry_click: Callback when an entry is clicked (receives entry ID)
            on_save_clipboard: Callback when Save Clipboard is clicked
        """
        self._on_search = on_search
        self._on_chat = on_chat
        self._on_quit = on_quit
        self._on_entry_click = on_entry_click
        self._on_save_clipboard = on_save_clipboard
        self._icon: Optional[pystray.Icon] = None

    def _get_stats_text(self, item=None) -> str:
        """Get statistics text for menu. Item arg passed by pystray for dynamic text."""
        try:
            stats = get_statistics()
            return (
                f"Total: {stats['total']} entries | "
                f"This week: {stats['this_week']} | "
                f"This month: {stats['this_month']}"
            )
        except Exception:
            return "Statistics unavailable"

    def _build_recent_entries_menu(self) -> list:
        """Build submenu for recent entries."""
        try:
            entries = get_recent_entries(limit=10)
            if not entries:
                return [pystray.MenuItem("No entries yet", None, enabled=False)]

            items = []
            for entry in entries:
                title = entry["title"][:40] + "..." if len(entry["title"]) > 40 else entry["title"]
                entry_id = entry["id"]
                items.append(
                    pystray.MenuItem(
                        title,
                        lambda _, eid=entry_id: self._handle_entry_click(eid),
                    )
                )
            return items
        except Exception:
            return [pystray.MenuItem("Error loading entries", None, enabled=False)]

    def _build_categories_menu(self) -> list:
        """Build submenu for categories."""
        try:
            categories = get_categories()
            if not categories:
                return [pystray.MenuItem("No categories yet", None, enabled=False)]

            items = []
            for category in categories:
                items.append(
                    pystray.MenuItem(
                        category,
                        lambda _, cat=category: self._handle_category_click(cat),
                    )
                )
            return items
        except Exception:
            return [pystray.MenuItem("Error loading categories", None, enabled=False)]

    def _handle_entry_click(self, entry_id: int) -> None:
        """Handle click on a recent entry."""
        if self._on_entry_click:
            self._on_entry_click(entry_id)

    def _handle_category_click(self, category: str) -> None:
        """Handle click on a category."""
        # For now, just open search - later could pre-filter
        if self._on_search:
            self._on_search()

    def _handle_search(self, icon, item) -> None:
        """Handle Search menu click."""
        if self._on_search:
            self._on_search()

    def _handle_chat(self, icon, item) -> None:
        """Handle AI Chat menu click."""
        if self._on_chat:
            self._on_chat()

    def _handle_save_clipboard(self, icon, item) -> None:
        """Handle Save Clipboard menu click."""
        if self._on_save_clipboard:
            self._on_save_clipboard()

    def _handle_open_folder(self, icon, item) -> None:
        """Open the database folder in explorer."""
        app_dir = get_app_dir()
        if sys.platform == "win32":
            os.startfile(str(app_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(app_dir)])
        else:
            subprocess.run(["xdg-open", str(app_dir)])

    def _handle_open_settings(self, icon, item) -> None:
        """Open the config file in default editor."""
        config_path = get_config_path()
        if sys.platform == "win32":
            os.startfile(str(config_path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(config_path)])
        else:
            subprocess.run(["xdg-open", str(config_path)])

    def _handle_quit(self, icon, item) -> None:
        """Handle Quit menu click."""
        if self._on_quit:
            self._on_quit()
        icon.stop()

    def _create_menu(self) -> pystray.Menu:
        """Create the tray menu."""
        config = Config()

        return pystray.Menu(
            pystray.MenuItem(
                f"Search ({config.hotkey})",
                self._handle_search,
                default=True,
            ),
            pystray.MenuItem(
                "AI Chat",
                self._handle_chat,
            ),
            pystray.MenuItem(
                "Save Clipboard to Memory",
                self._handle_save_clipboard,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Recent Entries",
                pystray.Menu(lambda: self._build_recent_entries_menu()),
            ),
            pystray.MenuItem(
                "Browse by Category",
                pystray.Menu(lambda: self._build_categories_menu()),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                self._get_stats_text,
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings", self._handle_open_settings),
            pystray.MenuItem("Open Database Folder", self._handle_open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._handle_quit),
        )

    def run(self) -> None:
        """Run the tray application (blocking)."""
        icon_image = create_placeholder_icon()

        # Get initial entry count for tooltip
        try:
            stats = get_statistics()
            initial_title = f"{constants.APP_NAME} - {stats['total']} entries"
        except Exception:
            initial_title = f"{constants.APP_NAME} - Right-click for menu"

        self._icon = pystray.Icon(
            name=constants.APP_NAME,
            icon=icon_image,
            title=initial_title,
            menu=self._create_menu(),
        )

        # Set up left-click to open search
        self._icon.run(setup=self._on_setup)

    def _on_setup(self, icon) -> None:
        """Called when icon is set up."""
        icon.visible = True

    def stop(self) -> None:
        """Stop the tray application."""
        if self._icon:
            self._icon.stop()

    def update_tooltip(self, entry_count: int) -> None:
        """Update the tray icon tooltip with entry count."""
        if self._icon:
            self._icon.title = f"{constants.APP_NAME} - {entry_count} entries"
