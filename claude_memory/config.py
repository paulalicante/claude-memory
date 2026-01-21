"""
Configuration management for Claude Memory app.
"""

import json
import os
from pathlib import Path
from typing import Any

from . import constants


def get_app_dir() -> Path:
    """Get the application directory (where this package is installed)."""
    return Path(__file__).parent.parent


def get_default_config() -> dict:
    """Return default configuration values."""
    app_dir = get_app_dir()
    return {
        "database_path": str(app_dir / constants.DEFAULT_DB_NAME),
        "hotkey": constants.DEFAULT_HOTKEY,
        "poll_interval_ms": constants.DEFAULT_POLL_INTERVAL_MS,
        "show_notifications": True,
        "start_on_startup": False,
        "session_timeout_hours": constants.SESSION_TIMEOUT_HOURS,
        # AI settings (BYOK - Bring Your Own Key)
        "ai_api_key": "",  # User must provide their own Anthropic API key
        "ai_model": constants.DEFAULT_AI_MODEL,
        "ai_enabled": True,
        # HTTP server for external integrations
        "http_server_enabled": True,
        "http_server_port": constants.DEFAULT_HTTP_SERVER_PORT,
    }


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_app_dir() / constants.DEFAULT_CONFIG_NAME


def load_config() -> dict:
    """Load configuration from file, creating with defaults if not exists."""
    config_path = get_config_path()
    defaults = get_default_config()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            # Merge with defaults (user config takes precedence)
            return {**defaults, **user_config}
        except (json.JSONDecodeError, IOError):
            # If config is corrupted, return defaults
            return defaults
    else:
        # Create config file with defaults
        save_config(defaults)
        return defaults


def save_config(config: dict) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a single configuration value."""
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set a single configuration value."""
    config = load_config()
    config[key] = value
    save_config(config)


class Config:
    """Configuration singleton for easy access throughout the app."""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config = load_config()
        return cls._instance

    def __getitem__(self, key: str) -> Any:
        return self._config.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self._config[key] = value
        save_config(self._config)

    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = load_config()

    @property
    def database_path(self) -> str:
        return self._config["database_path"]

    @property
    def hotkey(self) -> str:
        return self._config["hotkey"]

    @property
    def poll_interval_ms(self) -> int:
        return self._config["poll_interval_ms"]

    @property
    def show_notifications(self) -> bool:
        return self._config["show_notifications"]

    @property
    def session_timeout_hours(self) -> int:
        return self._config["session_timeout_hours"]

    @property
    def ai_api_key(self) -> str:
        return self._config.get("ai_api_key", "")

    @property
    def ai_model(self) -> str:
        return self._config.get("ai_model", constants.DEFAULT_AI_MODEL)

    @property
    def ai_enabled(self) -> bool:
        return self._config.get("ai_enabled", True)

    @property
    def http_server_enabled(self) -> bool:
        return self._config.get("http_server_enabled", True)

    @property
    def http_server_port(self) -> int:
        return self._config.get("http_server_port", constants.DEFAULT_HTTP_SERVER_PORT)
