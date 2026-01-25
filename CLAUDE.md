# Claude Memory

A Windows desktop application that captures and stores important information from Claude conversations with AI-powered memory management.

## What It Does

- Monitors clipboard for specially formatted `@@CLAUDE_MEMORY@@` blocks
- Automatically saves entries to SQLite database with substring search
- Provides search UI with checkboxes for multi-select operations
- Remove Duplicates feature - merges duplicate entries line-by-line
- HTML email viewing - preserves formatting from Gmail
- Runs in system tray with global hotkey access (Ctrl+Shift+M)
- Single-instance protection prevents multiple copies running
- Watchdog monitors keyboard hooks and auto-recovers
- Exposes MCP server for direct Claude integration
- HTTP server for browser extension integration
- PDF import with visual rendering

## Tech Stack

- **Python 3** with PyQt6 (modern UI), tkinter (legacy UI), pystray (tray), pyperclip (clipboard), keyboard (hotkeys)
- **SQLite** with FTS5 for full-text search
- **Anthropic SDK** for AI features (BYOK - user provides API key)
- **FastMCP** for Model Context Protocol server
- **PyMuPDF** for PDF text extraction

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Quick start (recommended)
Double-click start.bat

# Restart (kills old instance and starts fresh)
Double-click restart.bat

# Or run manually
python run.pyw

# Or with console output
python -m claude_memory.main

# MCP server (for Claude integration)
python mcp_server.py
```

## Project Structure

```
claude_memory/           # Main package
├── main.py             # Entry point & orchestration
├── config.py           # Configuration singleton
├── constants.py        # App-wide constants
├── database.py         # SQLite operations & FTS5
├── clipboard_watcher.py # Clipboard monitoring
├── notifications.py    # Toast notifications
├── ai_query.py         # Claude API integration
├── tray.py             # System tray UI
├── search_window.py    # Search/browse UI (tkinter - legacy)
├── search_window_pyqt.py # Search/browse UI (PyQt6 - new)
├── detail_window.py    # Detail/edit window (PyQt6)
├── chat_window.py      # AI chat UI
├── http_server.py      # HTTP server for browser extensions
└── pdf_handler.py      # PDF import and text extraction

gmail-memory-extension/  # Chrome extension for Gmail/web capture
├── manifest.json
├── content.js
├── background.js
└── popup.html

mcp_server.py           # MCP server exposing tools to Claude
run.pyw                 # Windows launcher (no console)
config.json             # User configuration
memory.db               # SQLite database
pdfs/                   # Stored PDF files
```

## Memory Block Format

Copy this format to clipboard and it auto-saves:

```
@@CLAUDE_MEMORY@@
{
  "title": "Required title",
  "content": "Required content",
  "category": "optional",
  "tags": "tag1, tag2"
}
@@END_MEMORY@@
```

## Configuration (config.json)

- `database_path`: Path to SQLite database
- `hotkey`: Global hotkey (default: `ctrl+shift+m`)
- `poll_interval_ms`: Clipboard poll interval (default: 500)
- `show_notifications`: Enable toast notifications
- `ai_api_key`: User's Anthropic API key
- `ai_model`: Model to use (default: `claude-3-haiku`)

## Key Patterns

- **Singleton config**: `Config` class for app-wide settings
- **Callback system**: Components communicate via callbacks
- **Threading**: Clipboard watcher, hotkey listener, notifications run in background
- **Session management**: Auto-creates sessions based on 4-hour inactivity gaps

## MCP Tools

The MCP server (`mcp_server.py`) exposes:
- `search_memories`, `get_memory`, `get_recent_memories`
- `get_memories_by_category`, `list_categories`, `get_memory_stats`
- `add_memory`, `ask_memories` (AI-powered Q&A)
- `archive_memory`, `unarchive_memory`, `get_archived_memories`

## HTTP Server

The app runs an HTTP server on port 5000 for browser extension communication:
- `POST /memory` - Add a new memory entry
- `GET /health` - Health check endpoint

## Browser Extension

The `gmail-memory-extension/` folder contains a Chrome extension for Gmail:

**Features:**
- Manual save button appears when viewing emails
- Click "💾 Save to Claude Memory" to capture email
- Preserves HTML formatting (colors, fonts, images, links)
- Auto-saves sent emails with prompt
- Stores both HTML (for viewing) and plain text (for search)

**Installation:**
1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `gmail-memory-extension/` folder
5. Open Gmail - button will appear when viewing emails

## Key Features

### Multi-Select with Checkboxes
- Enable multi-select mode with checkbox
- Checkboxes appear for each entry (no Ctrl+clicking!)
- Orange warning shows when multi-select is active
- Select multiple entries for bulk operations

### Remove Duplicates
- Select 2+ duplicate entries
- Click "Remove Duplicates"
- Merges content line-by-line, keeping only unique lines
- Creates new `[Merged]` entry and deletes originals
- Perfect for continuing conversations captured multiple times

### HTML Email Viewing
- Emails saved from Gmail preserve full formatting
- Click entry to auto-open in browser with styled layout
- Plain text preview shown in app for quick reference
- Search works on plain text content

### Smart Search
- Substring matching - "paulspain" finds "paulspainward"
- Searches in both title and content
- Category and date filtering
- Real-time results

### Stability Features
- **Single Instance**: Prevents multiple copies from running
- **Watchdog**: Monitors keyboard hooks, auto-recovers if lost
- **Crash Logging**: Writes errors to `crash.log` for debugging
- Handles desktop switching without crashing

## UI Migration to PyQt6 (In Progress)

### Current Status
A new PyQt6-based UI is being developed alongside the existing tkinter UI. The new design features:
- **Solarized Light color scheme** - Warm cream/beige backgrounds (#FDF6E3, #EEE8D5)
- **Custom title bar** - Frameless window with draggable custom chrome (Windows 10 compatible)
- **Dark sidebar** (#073642) with light cream buttons (#586E75) and accent blue (#268BD2)
- **No menu bar** - All actions consolidated in sidebar to avoid clutter
- **Modern controls** - Search with clear (X) button, styled dropdowns, rounded corners

### Files
- `claude_memory/search_window_pyqt.py` - New PyQt6 search window (✅ Complete)
- `claude_memory/detail_window.py` - Detail/edit window (⚠️ Needs PyQt6 version)
- `test_pyqt_ui.py` - Test launcher for PyQt6 UI

### Completed Features
- ✅ Custom title bar with minimize/maximize/close buttons
- ✅ Window dragging from title bar
- ✅ Solarized Light color scheme throughout
- ✅ Search field with clear (X) button and auto-refresh
- ✅ Category dropdown with visible arrow indicator
- ✅ Styled dropdown (dark button, light popup list)
- ✅ Results list with hover and selection states
- ✅ Database integration (search, recent entries, delete)
- ✅ Status bar with entry count

### Outstanding Tasks
- ⬜ Implement Quick Add dialog in PyQt6
- ⬜ Implement PDF import dialog in PyQt6
- ⬜ Port detail window to PyQt6 (currently uses placeholder)
- ⬜ Port chat window to PyQt6
- ⬜ Add multi-select checkboxes functionality
- ⬜ Implement "Remove Duplicates" feature in PyQt6
- ⬜ Add AI Summarize integration to PyQt6 UI
- ⬜ Implement auto-refresh timer
- ⬜ Update main.py to launch PyQt6 UI instead of tkinter
- ⬜ Test all functionality (tray integration, hotkeys, clipboard monitoring)
- ⬜ Migration path for existing users

### Color Reference (Solarized Light)
- Background cream: `#FDF6E3`
- Lighter cream: `#EEE8D5`
- Borders/dividers: `#D3CBB7`
- Dark sidebar: `#073642`
- Darker sidebar: `#002B36`
- Sidebar buttons: `#586E75`
- Lighter gray: `#657B83`
- Medium gray text: `#93A1A1`
- Accent blue: `#268BD2`
- Text on light: `#073642`
- Text on dark: `#FDF6E3`

## Constants

- Memory markers: `@@CLAUDE_MEMORY@@` / `@@END_MEMORY@@`
- Default hotkey: `ctrl+shift+m`
- HTTP server port: 8765 (dynamic)
- Single-instance lock port: 47283
- Session timeout: 4 hours
- Max AI tokens: 2048
