"""
Toast notifications for Claude Memory app.
"""

import threading
from typing import Callable, Optional

from .config import Config
from . import constants

# Try to import notification library
try:
    from plyer import notification as plyer_notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

# Fallback to win10toast if plyer not available
if not HAS_PLYER:
    try:
        from win10toast import ToastNotifier
        HAS_WIN10TOAST = True
        _toaster = ToastNotifier()
    except ImportError:
        HAS_WIN10TOAST = False
        _toaster = None


def notify(
    title: str,
    message: str,
    timeout: int = constants.TOAST_DURATION_SECONDS,
    callback: Optional[Callable] = None,
) -> None:
    """
    Show a toast notification.
    Runs in a separate thread to avoid blocking.
    """
    config = Config()
    if not config.show_notifications:
        return

    def _show():
        try:
            if HAS_PLYER:
                plyer_notification.notify(
                    title=title,
                    message=message,
                    app_name=constants.APP_NAME,
                    timeout=timeout,
                )
            elif HAS_WIN10TOAST and _toaster:
                _toaster.show_toast(
                    title,
                    message,
                    duration=timeout,
                    threaded=False,
                )
            else:
                # No notification library available, silently skip
                pass

            if callback:
                callback()
        except Exception:
            # Silently fail on notification errors
            pass

    # Run notification in background thread
    thread = threading.Thread(target=_show, daemon=True)
    thread.start()


def notify_saved(entry_title: str) -> None:
    """Show a notification that an entry was saved."""
    notify(
        title="Saved",
        message=entry_title[:100],  # Truncate long titles
    )


def notify_error(message: str) -> None:
    """Show an error notification."""
    notify(
        title="Claude Memory Error",
        message=message,
    )
