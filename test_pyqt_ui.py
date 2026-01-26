"""
Test launcher for PyQt6 Solarized UI
Run this to see the new design in action
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

# Add parent dir to path
sys.path.insert(0, '.')

from claude_memory.search_window_pyqt import SearchWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = SearchWindow()
    window.show()

    sys.exit(app.exec())
