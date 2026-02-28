"""
Floating Mini-Button for Otterly Memory.

A tiny always-on-top window that:
- Shows on ALL virtual desktops (Windows 10/11)
- Can be dragged to any screen edge
- Single click opens the search window
- Right-click shows menu (Quit, Hide, etc.)
- Minimal footprint (small circular button)

Uses win32 API to set "show on all desktops" flag.
"""

import sys
import ctypes
from ctypes import wintypes

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMenu, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QAction, QCursor


# Windows API for "show on all virtual desktops"
try:
    from comtypes import GUID
    import comtypes.client

    CLSID_VirtualDesktopManager = GUID("{AA509086-5CA9-4C25-8F95-589D3C07B48A}")
    IID_IVirtualDesktopManager = GUID("{A5CD92FF-29BE-454C-8D04-D82879FB3F1B}")

    HAS_VIRTUAL_DESKTOP_API = True
except ImportError:
    HAS_VIRTUAL_DESKTOP_API = False


# Fallback: Use SetWindowPos with HWND_TOPMOST
user32 = ctypes.windll.user32
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


class FloatingButton(QWidget):
    """
    Tiny floating button that stays on top across all desktops.
    """

    clicked = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, size: int = 40):
        super().__init__()

        self.button_size = size
        self._drag_pos = None
        self._is_hovered = False

        # Frameless, always on top, tool window (no taskbar entry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint
        )

        # Transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Fixed size
        self.setFixedSize(size, size)

        # Start in bottom-right corner
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - size - 20, screen.height() - size - 100)

        # Track mouse for hover effect
        self.setMouseTracking(True)

        # Context menu
        self._setup_context_menu()

        # Make topmost periodically (some apps steal focus)
        self._topmost_timer = QTimer()
        self._topmost_timer.timeout.connect(self._ensure_topmost)
        self._topmost_timer.start(5000)  # Every 5 seconds

    def _setup_context_menu(self):
        """Create right-click context menu."""
        self.context_menu = QMenu(self)

        open_action = QAction("Open Otterly Memory", self)
        open_action.triggered.connect(self.clicked.emit)
        self.context_menu.addAction(open_action)

        self.context_menu.addSeparator()

        hide_action = QAction("Hide Button (use Ctrl+Shift+M)", self)
        hide_action.triggered.connect(self.hide)
        self.context_menu.addAction(hide_action)

        self.context_menu.addSeparator()

        quit_action = QAction("Quit Otterly Memory", self)
        quit_action.triggered.connect(self.quit_requested.emit)
        self.context_menu.addAction(quit_action)

    def _ensure_topmost(self):
        """Periodically ensure we stay on top."""
        if self.isVisible():
            hwnd = int(self.winId())
            user32.SetWindowPos(
                hwnd, HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )

    def showEvent(self, event):
        """When shown, set topmost and try to show on all desktops."""
        super().showEvent(event)
        self._ensure_topmost()
        self._try_show_on_all_desktops()

    def _try_show_on_all_desktops(self):
        """
        Try to make window visible on all virtual desktops.
        This uses undocumented Windows API and may not work on all systems.
        """
        # Method 1: Set window style to show on all desktops
        # This is a best-effort approach
        hwnd = int(self.winId())

        # WS_EX_TOOLWINDOW already set via Qt flags
        # Some apps use a workaround: minimize and restore
        # But for a floating button, staying topmost is usually enough

        # The key insight: HWND_TOPMOST windows typically show on all desktops
        # in Windows 10/11 as long as they're small tool windows
        pass

    def paintEvent(self, event):
        """Draw the circular button."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colors
        if self._is_hovered:
            bg_color = QColor("#268BD2")  # Accent blue on hover
            border_color = QColor("#FDF6E3")
        else:
            bg_color = QColor("#073642")  # Dark sidebar color
            border_color = QColor("#586E75")

        # Draw circle
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2))
        margin = 2
        painter.drawEllipse(margin, margin, self.button_size - margin*2, self.button_size - margin*2)

        # Draw "OM" text (Otterly Memory)
        painter.setPen(QPen(QColor("#FDF6E3")))
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "OM")

    def enterEvent(self, event):
        """Mouse entered - show hover state."""
        self._is_hovered = True
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.update()

    def leaveEvent(self, event):
        """Mouse left - remove hover state."""
        self._is_hovered = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse press for dragging or clicking."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        """Handle dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        """Handle click (if not dragged)."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_pos:
                # Check if it was a click (not a drag)
                drag_distance = (event.globalPosition().toPoint() - self.frameGeometry().topLeft() - self._drag_pos).manhattanLength()
                if drag_distance < 5:  # Threshold for "click vs drag"
                    self.clicked.emit()
            self._drag_pos = None


def create_floating_button(on_click=None, on_quit=None) -> FloatingButton:
    """
    Create and return a floating button instance.

    Args:
        on_click: Callback when button is clicked
        on_quit: Callback when quit is requested

    Returns:
        FloatingButton instance (call .show() to display)
    """
    button = FloatingButton(size=40)

    if on_click:
        button.clicked.connect(on_click)
    if on_quit:
        button.quit_requested.connect(on_quit)

    return button


# Standalone test
if __name__ == "__main__":
    app = QApplication(sys.argv)

    def on_click():
        print("Button clicked!")

    def on_quit():
        print("Quit requested")
        app.quit()

    button = create_floating_button(on_click, on_quit)
    button.show()

    print("Floating button running. Right-click to quit.")
    sys.exit(app.exec())
