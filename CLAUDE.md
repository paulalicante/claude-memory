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
├── pdf_handler.py      # PDF import and text extraction
├── file_indexer.py     # File discovery and indexing system
└── discovery_dialog.py # File discovery UI dialog (PyQt6)

gmail-memory-extension/  # Chrome extension for Gmail/web capture
├── manifest.json
├── content.js
├── background.js
└── popup.html

vscode-memory-extension/ # VS Code extension for conversation capture
├── package.json
├── extension.js
└── README.md

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

## Database Schema

### Core Tables
- `entries` - Memory entries with title, content, category, tags
- `entries_fts` - FTS5 virtual table for full-text search

### File Indexing Tables (Added 2026-01)
- `watched_folders` - Folders to monitor and index
  - Tracks folder path, monitoring status, last scan date, file count
- `indexed_files` - Lightweight references to files on disk
  - Stores file path, name, type, size, modified date, content preview
  - Foreign key to `watched_folders` with CASCADE delete
- `files_fts` - FTS5 virtual table for file content search
  - Indexes file_name, file_path, content_preview
  - Auto-synced with triggers on INSERT/UPDATE/DELETE

### Image Search Tables (Added 2026-01)
- `persons` - Known people (tagged faces)
  - Stores name and reference face embedding (128-dim BLOB)
- `face_embeddings` - Detected faces in images
  - Stores image path, face embedding (128-dim), bounding box coordinates
  - Foreign key to `persons` for tagged faces
  - Indexed by person_id and image_path
- `clip_embeddings` - Semantic scene embeddings
  - Stores image path and CLIP embedding (512-dim BLOB)
  - One embedding per image for scene/semantic search

### Functions
- `unified_search()` - Searches both memories and indexed files
- `refresh_folder_index()` - Re-scans and updates file content
- `auto_refresh_placeholder_files()` - Updates old placeholder content on startup

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

## VS Code Extension

The `vscode-memory-extension/` folder contains a VS Code extension for capturing conversations:

**Features:**
- Status bar button "💾 Save to CM" in VS Code
- One-click save of current Claude Code conversation
- Automatically finds most recent conversation file
- Formats with role markers ([USER], [ASSISTANT])
- Posts to HTTP server on localhost:8765

**Installation:**
1. Copy the `vscode-memory-extension/` folder to `%USERPROFILE%\.vscode\extensions\`
2. Restart VS Code
3. The "💾 Save to CM" button will appear in the status bar (bottom right)
4. Click to save your current conversation

**Alternative:** Use Command Palette (Ctrl+Shift+P) and search for "Save Conversation to Claude Memory"

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
- Hover preview with search term highlighting
- Unified search across memories and indexed files

### Universal File Indexing
- **File Discovery Dialog**: Browse and select folders to index
- **Recursive scanning**: Option to scan all subfolders
- **File type selection**: Choose which file types to index (.txt, .md, .pdf, .docx, .xlsx, code files, etc.)
- **Full content extraction**: Extracts text from Word docs, Excel sheets, and PDFs
- **Lightweight indexing**: Stores file references and previews, not full content
- **Folder management**: View indexed folders, refresh content, remove folders
- **Auto-refresh**: Automatically updates placeholder content on startup
- **Unified search results**: Shows both 📝 memories and 📄 files with visual distinction
- **File actions**: Open files in default app or import as memory entries

### Conversation Capture
- **VS Code Extension**: Status bar button "💾 Save to CM" for one-click conversation saving (recommended)
- **Desktop App Button**: "💬 Save Conversation" button in PyQt6 UI
- Finds most recent conversation transcript (.jsonl format)
- Parses all messages and formats with role markers
- Posts to HTTP server or saves directly to database
- Shows confirmation with message count

### Image Search (Face Recognition + CLIP)
- **Semantic search**: Find images by person AND/OR scene description
- **Face recognition**: "Michelle" finds all photos of Michelle
- **Scene search**: "beach" finds beach scenes using CLIP embeddings
- **Combined queries**: "Michelle on the beach" requires both person and scene match
- **Auto-tagging**: Tag one face, automatically find all similar faces
- **128-dim face embeddings**: Using face_recognition library
- **512-dim CLIP embeddings**: Semantic scene understanding
- **Tolerance threshold**: Adjustable face matching strictness

### Stability Features
- **Single Instance**: Prevents multiple copies from running
- **Watchdog**: Monitors keyboard hooks, auto-recovers if lost
- **Crash Logging**: Writes errors to `crash.log` for debugging
- **Background threads**: File scanning and indexing run without blocking UI
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
- ✅ Hover preview with fixed z-order and search term highlighting
- ✅ Database integration (search, recent entries, delete)
- ✅ Status bar with entry count (shows memories + files separately)
- ✅ Detail window with text/PDF/HTML viewing
- ✅ Quick Add dialog for creating entries
- ✅ PDF Import dialog with preview
- ✅ Multi-select checkboxes functionality (solid green fill when checked)
- ✅ Remove Duplicates feature (line-by-line merge)
- ✅ Auto-refresh timer (2-second interval)
- ✅ File Discovery Dialog with folder browser and file type selection
- ✅ Unified search (memories + indexed files with 📝/📄 icons)
- ✅ File actions (Open File, Import to Memory)
- ✅ Folder refresh and management in Discovery Dialog
- ✅ Auto-refresh for placeholder content on startup
- ✅ Save Conversation button (captures Claude Code transcripts)
- ✅ Background threading for file scanning and indexing

### Outstanding Tasks
- ⬜ Port chat window to PyQt6
- ⬜ Add AI Summarize integration to PyQt6 UI
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

## File Indexing System

### Supported File Types
The file indexer supports the following file types:
- **Plain text**: .txt, .md, .log, .csv, .json, .xml, .yaml, .yml
- **Documents**: .docx, .doc (Word documents with full text extraction)
- **Spreadsheets**: .xlsx, .xls (Excel - extracts first 20 rows from active sheet)
- **PDFs**: .pdf (extracts text from first 3 pages)
- **Code files**: .py, .js, .java, .cpp, .c, .h, .cs, .html, .css, .sql

### Content Extraction
- **Plain text files**: Read directly with UTF-8/Latin-1 encoding fallback
- **Word documents**: Uses `python-docx` to extract all paragraph text
- **Excel spreadsheets**: Uses `openpyxl` to read cell values from active sheet
- **PDFs**: Uses `PyMuPDF` (fitz) to extract text from first 3 pages
- All extracts limited to 1000 characters for preview/search

### Database Storage
- Files are NOT duplicated into the database
- Only lightweight references stored: path, name, type, size, modified date
- Content preview (first 1000 chars) stored for search
- Uses FTS5 for fast full-text search across file content

### Discovery Dialog Workflow
1. **Choose Folder**: Browse to select folder, option for recursive scan
2. **Select File Types**: After scan, choose which file types to index
3. **Monitoring Options**: Enable/disable active monitoring (watchdog)
4. **Review Indexed**: View all indexed folders, refresh or remove as needed

### Requirements Added
- `python-docx>=0.8.11` - Word document parsing
- `openpyxl>=3.1.0` - Excel spreadsheet parsing
- `watchdog>=3.0.0` - File system monitoring (future use)
