"""
Constants for Claude Memory app.
"""

# Magic markers for clipboard detection
MEMORY_START_MARKER = "@@CLAUDE_MEMORY@@"
MEMORY_END_MARKER = "@@END_MEMORY@@"

# Default paths
DEFAULT_DB_NAME = "memory.db"
DEFAULT_CONFIG_NAME = "config.json"
DEFAULT_BACKUP_DIR = "backups"

# Clipboard polling interval (milliseconds)
DEFAULT_POLL_INTERVAL_MS = 500

# Session timeout (hours) - new session if gap exceeds this
SESSION_TIMEOUT_HOURS = 4

# Global hotkey
DEFAULT_HOTKEY = "ctrl+shift+m"

# App info
APP_NAME = "Claude Memory"
APP_VERSION = "1.1.0"

# Toast notification settings
TOAST_DURATION_SECONDS = 3

# Search window dimensions
SEARCH_WINDOW_WIDTH = 800
SEARCH_WINDOW_HEIGHT = 600

# Date range filter options
DATE_FILTERS = {
    "All Time": None,
    "Today": 0,
    "Last 7 Days": 7,
    "Last 30 Days": 30,
    "Last 90 Days": 90,
}

# HTTP Server Configuration
DEFAULT_HTTP_SERVER_PORT = 8765

# AI Configuration
AI_MODELS = {
    "claude-3-haiku": "claude-3-haiku-20240307",  # Cheapest, fast
    "claude-3-sonnet": "claude-3-5-sonnet-20241022",  # Better quality
}
DEFAULT_AI_MODEL = "claude-3-haiku"
AI_MAX_TOKENS = 2048

# Chat window dimensions
CHAT_WINDOW_WIDTH = 700
CHAT_WINDOW_HEIGHT = 500
