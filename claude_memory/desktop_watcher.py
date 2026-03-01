"""
Claude Desktop conversation watcher via Windows UI Automation.
Reads conversation text from Claude Desktop using accessibility APIs.
Runs as a background thread inside the Otterly Memory system tray app.
"""

import sys
import time
import json
import ctypes
import ctypes.wintypes
import hashlib
import threading
import logging
from datetime import datetime
from typing import Optional, Callable, List, Dict

from .database import add_entry
from .notifications import notify_saved

log = logging.getLogger("otterly-desktop")

# Also log to file for debugging (since tray app has no console)
_log_file = None
try:
    import os
    _log_dir = os.path.dirname(os.path.abspath(__file__))
    _log_file = os.path.join(os.path.dirname(_log_dir), "desktop_watcher.log")
    _fh = logging.FileHandler(_log_file, encoding='utf-8')
    _fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
    log.addHandler(_fh)
    log.setLevel(logging.DEBUG)
except Exception:
    pass

# ── Windows UI Automation ───────────────────────────────────────────
# Lazy-loaded to avoid import errors on non-Windows or when comtypes missing
_comtypes_loaded = False
_IUIAutomation = None
_TreeScope_Children = None
_TreeScope_Descendants = None
_GUID = None


def _ensure_comtypes():
    """Lazy-load comtypes and generate UIAutomation type library."""
    global _comtypes_loaded, _IUIAutomation, _TreeScope_Children, _TreeScope_Descendants, _GUID
    if _comtypes_loaded:
        return True
    try:
        import comtypes
        import comtypes.client
        from comtypes import GUID
        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen.UIAutomationClient import (
            IUIAutomation, TreeScope_Children, TreeScope_Descendants
        )
        _IUIAutomation = IUIAutomation
        _TreeScope_Children = TreeScope_Children
        _TreeScope_Descendants = TreeScope_Descendants
        _GUID = GUID
        _comtypes_loaded = True
        return True
    except Exception as e:
        log.warning(f"Could not load UI Automation: {e}")
        return False


# ── Configuration ───────────────────────────────────────────────────
POLL_INTERVAL = 5  # seconds between scans
WINDOW_TITLE = "Claude"
WINDOW_CLASS = "Chrome_WidgetWin_1"

# UIA Control Type IDs
UIA_NamePropertyId = 30005
UIA_ClassNamePropertyId = 30012
UIA_ControlTypePropertyId = 30003
UIA_TextControlTypeId = 50020
UIA_ButtonControlTypeId = 50000
UIA_GroupControlTypeId = 50026
UIA_ListItemControlTypeId = 50007
UIA_HyperlinkControlTypeId = 50005
UIA_StatusBarControlTypeId = 50017


# ── Accessibility Setup ────────────────────────────────────────────

def enable_accessibility():
    """Enable Chromium accessibility via screen reader flag + registry."""
    SPI_SETSCREENREADERACTIVE = 0x0047
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02

    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETSCREENREADERACTIVE, 1, None,
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )

    try:
        import winreg
        for key_path in [
            r"Software\Google\Chrome\Accessibility",
            r"Software\Anthropic\Claude\Accessibility",
        ]:
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
                winreg.SetValueEx(key, "ForceRendererAccessibility", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
            except Exception:
                pass
    except Exception:
        pass

    log.debug("Accessibility flags set")


def disable_screen_reader_flag():
    """Clear the screen reader flag on shutdown."""
    SPI_SETSCREENREADERACTIVE = 0x0047
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETSCREENREADERACTIVE, 0, None, 0x01 | 0x02
    )


# ── UI Tree Reading ────────────────────────────────────────────────

def _get_uia():
    """Get UI Automation COM object."""
    return __import__('comtypes').client.CreateObject(
        _GUID("{FF48DBA4-60EF-4201-AA87-54103EEF594E}"),
        interface=_IUIAutomation
    )


def _find_claude_window(uia):
    """Find the Claude Desktop window."""
    root = uia.GetRootElement()
    name_cond = uia.CreatePropertyCondition(UIA_NamePropertyId, WINDOW_TITLE)
    class_cond = uia.CreatePropertyCondition(UIA_ClassNamePropertyId, WINDOW_CLASS)
    combined = uia.CreateAndCondition(name_cond, class_cond)
    return root.FindFirst(_TreeScope_Children, combined)


def _walk_tree(uia, element, depth=0, max_depth=30):
    """Walk the UI tree and collect elements with metadata."""
    if depth > max_depth:
        return []

    results = []
    try:
        name = element.CurrentName or ""
        class_name = element.CurrentClassName or ""
        control_type = element.CurrentControlType
        results.append({
            'depth': depth, 'name': name,
            'class': class_name, 'type': control_type,
            'element': element
        })
    except Exception:
        return results

    try:
        walker = uia.RawViewWalker
        child = walker.GetFirstChildElement(element)
        while child:
            try:
                results.extend(_walk_tree(uia, child, depth + 1, max_depth))
                child = walker.GetNextSiblingElement(child)
            except Exception:
                break
    except Exception:
        pass

    return results


# ── Conversation Parsing ───────────────────────────────────────────

_UI_CHROME_TEXTS = {
    "Menu", "Open sidebar", "Back", "Forward", "Chat", "Cowork", "Code",
    "Sidebar", "Done", "Show more", "Copy to clipboard", "Retry",
    "Scroll to bottom", "Reply...", "Toggle menu", "Share chat",
    "Content", "Notifications (F8)",
    "Claude is AI and can make mistakes. Please double-check responses.",
    "O", "F", "Extended", "Thinking",
}

_THINKING_PREFIXES = (
    "Devised", "Validated", "Identified", "Acknowledged", "Pivoted",
    "Investigated", "Recognized", "Explored", "Diagnosed", "Architected",
    "Deliberated", "Charted", "Reconnoitering", "Excavated", "Interpreted",
    "Weighed", "Evaluated", "Pursued", "Reconciled", "Outlined",
    "Strategized", "Analyzed",
)


def _is_ui_chrome(name, cls):
    if name in _UI_CHROME_TEXTS:
        return True
    if len(name) <= 2 and not name.isalpha():
        return True
    if ("Opus" in name or "Sonnet" in name or "Haiku" in name) and \
       ("Extended" in name or "4." in name):
        return True
    return False


def _is_thinking_block(name, elements, idx):
    if not name:
        return False
    if name.startswith(_THINKING_PREFIXES):
        return True
    if idx + 1 < len(elements) and elements[idx + 1]['type'] == UIA_StatusBarControlTypeId:
        return True
    return False


def _determine_role(el, elements, idx):
    depth = el['depth']
    j = idx + 1
    if j < len(elements) and elements[j]['depth'] == depth + 1:
        child_class = elements[j].get('class', '')
        if 'text-xs' in child_class and 'text-text-500' in child_class:
            return 'user'
    return 'assistant'


def _extract_title(elements):
    for el in elements:
        if el['type'] == UIA_ButtonControlTypeId:
            cls = el.get('class', '')
            if '!text-text-300' in cls and el['name']:
                return el['name']
    return "Untitled"


def _parse_conversation(elements) -> List[Dict]:
    """Parse flat element list into conversation turns."""
    messages = []
    current_texts = []
    i = 0

    while i < len(elements):
        el = elements[i]
        name = el['name']
        cls = el['class']
        ctrl_type = el['type']

        # "Message actions" GroupBox = end of a message
        if ctrl_type == UIA_GroupControlTypeId and name == "Message actions":
            if current_texts:
                role = _determine_role(el, elements, i)
                text = " ".join(current_texts).strip()
                if text and len(text) > 1:
                    messages.append({'role': role, 'content': text})
                current_texts = []
            my_depth = el['depth']
            i += 1
            while i < len(elements) and elements[i]['depth'] > my_depth:
                i += 1
            continue

        if ctrl_type == UIA_TextControlTypeId and name:
            if not _is_ui_chrome(name, cls):
                current_texts.append(name)

        elif ctrl_type == UIA_ListItemControlTypeId and name:
            current_texts.append(f"• {name}")

        elif ctrl_type == UIA_ButtonControlTypeId and _is_thinking_block(name, elements, i):
            i += 1
            while i < len(elements) and elements[i]['type'] == UIA_StatusBarControlTypeId:
                i += 1
                if i < len(elements):
                    my_depth = elements[i - 1]['depth']
                    while i < len(elements) and elements[i]['depth'] > my_depth:
                        i += 1
            continue

        elif ctrl_type == UIA_ButtonControlTypeId and name in ("Result", "Script"):
            i += 1
            continue

        elif ctrl_type == UIA_HyperlinkControlTypeId and name:
            if not name.startswith("Claude is AI"):
                current_texts.append(name)

        i += 1

    if current_texts:
        text = " ".join(current_texts).strip()
        if text and len(text) > 1:
            messages.append({'role': 'unknown', 'content': text})

    return messages


# ── Desktop Watcher Class ──────────────────────────────────────────

class DesktopWatcher:
    """
    Watches Claude Desktop for new conversation turns via UI Automation.
    Runs in a background thread, saves directly to SQLite via database.add_entry().
    """

    def __init__(self, on_save: Optional[Callable[[dict], None]] = None):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_save = on_save
        self._last_hash = None
        self._last_message_count = 0
        self._saved_pairs: set = set()
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        log.info(f"Desktop watcher {'enabled' if value else 'disabled'}")

    def start(self) -> None:
        """Start the watcher thread."""
        if self._running:
            return

        if not _ensure_comtypes():
            log.warning("Desktop watcher disabled: comtypes not available")
            return

        enable_accessibility()
        log.info("Desktop watcher started (polling every %ds)", POLL_INTERVAL)

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._running = False
        # Don't join — thread is daemon, will die with process
        self._thread = None
        try:
            disable_screen_reader_flag()
        except Exception:
            pass
        log.info("Desktop watcher stopped")

    def _watch_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                if self._enabled:
                    self._poll_once()
            except Exception as e:
                log.error(f"Desktop watcher error: {e}")

            time.sleep(POLL_INTERVAL)

    def _poll_once(self) -> None:
        """Single poll cycle: scan, detect changes, save new turns."""
        try:
            uia = _get_uia()
        except Exception as e:
            log.debug(f"Could not create UIA: {e}")
            return

        window = _find_claude_window(uia)
        if not window:
            return  # Claude Desktop not open, silently skip

        elements = _walk_tree(uia, window)
        if len(elements) < 20:
            return  # Accessibility not active yet

        title = _extract_title(elements)
        messages = _parse_conversation(elements)

        # Change detection via hash
        content_hash = hashlib.md5(
            json.dumps(messages, sort_keys=True).encode()
        ).hexdigest()

        if content_hash == self._last_hash:
            return  # Nothing changed

        self._last_hash = content_hash
        new_count = len(messages)

        if new_count != self._last_message_count:
            log.debug(f"Message count changed: {new_count} (was {self._last_message_count})")
        else:
            log.debug(f"Content changed (same count: {new_count})")

        self._save_new_turns(messages, title)
        self._last_message_count = new_count

    @staticmethod
    def _make_title(content: str, max_len: int = 60) -> str:
        """Generate a descriptive title from conversation content."""
        import re

        # 1. Try file names
        for m in re.finditer(r'\b([a-zA-Z_][\w-]*\.(py|js|ts|json|md|html|css|dart|yaml))\b', content):
            return m.group(1)

        # 2. Try abbreviations/tech terms
        skip = {'THE','AND','FOR','BUT','NOT','YOU','ALL','CAN','HAS','ARE','HOW','LET','NEW','NOW','WHO','USE','WILL','HAVE','FROM','THAT','THEY','JUST','ALSO','WHAT','WITH','THIS','BEEN','THAN','VERY','WHEN','DONE','HERE','MUST','SURE','WELL','KNOW','NEED','WANT','RIGHT','DOES','BACK','ONLY','AFTER','ABOUT','COULD'}
        for m in re.finditer(r'\b([A-Z][A-Z0-9]{2,}[a-z]*|[A-Z][a-z]+[A-Z]\w*)\b', content):
            term = m.group(1)
            if term.upper() not in skip and len(term) >= 3:
                return term

        # 3. Try first meaningful Human message
        human_match = re.search(r'\*\*Human:\*\*\s*\n(.+?)(?:\n---|\n\*\*)', content, re.DOTALL)
        if human_match:
            msg = human_match.group(1).strip()
            generic = {'continue','yes','no','ok','yes please','go ahead','sure','next','thanks'}
            if msg and len(msg) >= 8 and msg.lower() not in generic:
                return msg[:max_len] + ('...' if len(msg) > max_len else '')

        # 4. Try first sentence of Assistant response
        asst_match = re.search(r'\*\*Assistant:\*\*\s*\n(.+?)(?:\n---|\n\*\*|\Z)', content, re.DOTALL)
        if asst_match:
            msg = asst_match.group(1).strip()
            sentence_end = re.search(r'[.!?\n]', msg)
            if sentence_end:
                msg = msg[:sentence_end.start()].strip()
            msg = re.sub(r'^(The user|User)\s+', '', msg).strip()
            if msg and len(msg) >= 8:
                return msg[:max_len] + ('...' if len(msg) > max_len else '')

        # 5. Fallback
        return f"Desktop conversation ({datetime.now().strftime('%H:%M')})"

    def _save_new_turns(self, messages: List[Dict], title: str) -> None:
        """Save new user→assistant pairs to the database."""
        i = 0
        while i < len(messages) - 1:
            if messages[i]['role'] == 'user':
                j = i + 1
                assistant_parts = []
                is_complete = True
                # Accept 'assistant' or 'unknown' (streaming/incomplete responses)
                while j < len(messages) and messages[j]['role'] in ('assistant', 'unknown'):
                    if messages[j]['role'] == 'unknown':
                        is_complete = False  # Still streaming
                    assistant_parts.append(messages[j]['content'])
                    j += 1

                # If incomplete (still streaming) AND this is the last pair, skip it
                # It will be saved on next poll when the response completes
                if not is_complete and j >= len(messages):
                    i = j
                    continue

                if assistant_parts:
                    user_text = messages[i]['content'][:2000]
                    assistant_text = " ".join(assistant_parts)[:2000]

                    pair_hash = hashlib.md5(
                        f"{user_text[:100]}|{assistant_text[:100]}".encode()
                    ).hexdigest()

                    if pair_hash not in self._saved_pairs:
                        try:
                            content = f"**Human:**\n{user_text}\n\n**Assistant:**\n{assistant_text}"
                            entry_title = self._make_title(content)
                            entry_id = add_entry(
                                title=entry_title,
                                content=content,
                                category="conversation",
                                tags="auto-saved,desktop",
                            )
                            self._saved_pairs.add(pair_hash)
                            log.info(f"Saved: '{user_text[:50]}...'")

                            if self._on_save:
                                self._on_save({
                                    "id": entry_id,
                                    "title": title,
                                    "source": "desktop"
                                })
                        except Exception as e:
                            log.warning(f"Failed to save turn: {e}")

                i = j
                continue
            i += 1
