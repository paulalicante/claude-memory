"""
Clipboard monitoring for Claude Memory app.
Watches for @@CLAUDE_MEMORY@@ blocks and saves them to database.
"""

import json
import re
import threading
from typing import Callable, Optional

import pyperclip

from . import constants
from .config import Config
from .database import add_entry
from .notifications import notify_saved, notify_error


class ClipboardWatcher:
    """
    Watches the clipboard for Claude Memory blocks.
    Runs in background thread, polls at configured interval.
    """

    def __init__(self, on_save: Optional[Callable[[dict], None]] = None):
        """
        Initialize the clipboard watcher.

        Args:
            on_save: Optional callback when an entry is saved. Receives the entry dict.
        """
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_clipboard = ""
        self._on_save = on_save
        self._config = Config()

    def start(self) -> None:
        """Start watching the clipboard."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching the clipboard."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _watch_loop(self) -> None:
        """Main loop that polls the clipboard."""
        while self._running:
            try:
                self._check_clipboard()
            except Exception:
                # Silently ignore clipboard errors
                pass

            # Wait for next poll
            interval_sec = self._config.poll_interval_ms / 1000.0
            threading.Event().wait(interval_sec)

    def _check_clipboard(self) -> None:
        """Check clipboard for memory blocks."""
        try:
            current = pyperclip.paste()
        except Exception:
            return

        # Skip if unchanged
        if current == self._last_clipboard:
            return

        self._last_clipboard = current

        # Check for memory block
        entry = self._parse_memory_block(current)
        if entry:
            self._save_entry(entry)

    def _parse_memory_block(self, text: str) -> Optional[dict]:
        """
        Parse a Claude Memory block from text.
        Returns parsed dict or None if not a valid block.
        """
        # Check for markers
        if constants.MEMORY_START_MARKER not in text:
            return None
        if constants.MEMORY_END_MARKER not in text:
            return None

        # Extract JSON between markers
        pattern = re.compile(
            re.escape(constants.MEMORY_START_MARKER)
            + r"\s*(\{.*?\})\s*"
            + re.escape(constants.MEMORY_END_MARKER),
            re.DOTALL,
        )
        match = pattern.search(text)
        if not match:
            return None

        json_str = match.group(1)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            notify_error("Invalid JSON in memory block")
            return None

        # Validate required fields
        if "title" not in data or not data["title"]:
            notify_error("Memory block missing title")
            return None
        if "content" not in data or not data["content"]:
            notify_error("Memory block missing content")
            return None

        # Normalize tags to comma-separated string
        tags = data.get("tags")
        if isinstance(tags, list):
            tags = ", ".join(str(t) for t in tags)
        data["tags"] = tags

        return data

    def _save_entry(self, entry: dict) -> None:
        """Save an entry to the database."""
        try:
            entry_id = add_entry(
                title=entry["title"],
                content=entry["content"],
                category=entry.get("category"),
                tags=entry.get("tags"),
                source_conversation=entry.get("source_conversation"),
            )

            # Show notification
            notify_saved(entry["title"])

            # Replace clipboard with just the title
            try:
                pyperclip.copy(entry["title"])
                self._last_clipboard = entry["title"]
            except Exception:
                pass

            # Call callback if provided
            if self._on_save:
                entry["id"] = entry_id
                self._on_save(entry)

        except Exception as e:
            notify_error(f"Failed to save: {str(e)[:50]}")
