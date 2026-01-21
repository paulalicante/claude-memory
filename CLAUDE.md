# Claude Memory

A Windows desktop application that captures and stores important information from Claude conversations with AI-powered memory management.

## What It Does

- Monitors clipboard for specially formatted `@@CLAUDE_MEMORY@@` blocks
- Automatically saves entries to SQLite database with full-text search (FTS5)
- Provides search UI, category filtering, and AI-powered natural language queries
- Runs in system tray with global hotkey access
- Exposes MCP server for direct Claude integration

## Tech Stack

- **Python 3** with tkinter (UI), pystray (tray), pyperclip (clipboard), keyboard (hotkeys)
- **SQLite** with FTS5 for full-text search
- **Anthropic SDK** for AI features (BYOK - user provides API key)
- **FastMCP** for Model Context Protocol server

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app (no console)
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
├── search_window.py    # Search/browse UI
└── chat_window.py      # AI chat UI

mcp_server.py           # MCP server exposing tools to Claude
run.pyw                 # Windows launcher (no console)
config.json             # User configuration
memory.db               # SQLite database
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

## Constants

- Memory markers: `@@CLAUDE_MEMORY@@` / `@@END_MEMORY@@`
- Default hotkey: `ctrl+shift+m`
- Session timeout: 4 hours
- Max AI tokens: 2048
