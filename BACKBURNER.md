# Otterly Memory — Backburner

Tasks to work on later. Not urgent, not forgotten.

---

## Move search window to current virtual desktop
**Added:** 2026-03-01
**Why:** Clicking the OM floating button switches you to the desktop where the main window lives instead of bringing it to your current desktop
**Notes:** Tried HWND_TOPMOST trick and Qt Tool flag — neither worked reliably. Windows Virtual Desktop API is undocumented. Option 2 would be a mini-search popup that runs on current desktop.

---

## AI-powered title generation (expensive)
**Added:** 2026-03-01
**Why:** Topic extraction catches ~98% but some entries still get generic titles. AI could generate perfect titles but costs money per entry.
**Notes:** Could run as a nightly batch on entries that still have fallback titles. Use Haiku to keep costs low.

---

## Title extraction still needs work
**Added:** 2026-03-01
**Why:** Some titles are single generic keywords like "update" or just the first user message truncated. Could be smarter about combining multiple signals.
**Notes:** Consider: weighting keywords by frequency, using TF-IDF, or extracting noun phrases.

---

## Web interface (localhost)
**Added:** 2026-03-01
**Why:** Would allow accessing Otterly Memory from any browser on any desktop without the virtual desktop switching problem
**Notes:** Flask web UI on localhost:8765 alongside the existing API. Search, browse, add entries.

---

## Claude Desktop extension (.mcpb) testing
**Added:** 2026-03-01
**Why:** Built otterly-memory-mcpb but haven't tested installation in Claude Desktop app yet
**Notes:** Extension is packaged and ready at otterly-memory-mcpb/. Needs: install in Claude Desktop, test auto_save prompt, verify database writes.

---

## Finish PyQt6 migration
**Added:** 2026-03-01
**Why:** Main app still launches PyQt6 but some dialogs/features may still reference tkinter
**Status:** From CLAUDE.md outstanding tasks:
- Update main.py to launch PyQt6 UI instead of tkinter
- Test all functionality (tray integration, hotkeys, clipboard monitoring)
- Migration path for existing users

---

## Otter logo/icon
**Added:** 2026-03-01
**Why:** App needs a proper icon for taskbar, system tray, Start Menu. Currently has no custom icon.
**Notes:** Ideas: otter head silhouette, otter holding glowing orb (memory), OM monogram. Need .ico file for Windows.

---

## Retitle script as scheduled task
**Added:** 2026-03-01
**Why:** New entries from desktop watcher and browser extension may still get bad titles. Could run retitle_conversations.py periodically.
**Notes:** Could hook into the observer's midnight run.
