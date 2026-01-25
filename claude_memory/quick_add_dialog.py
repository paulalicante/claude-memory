"""
Quick Add dialog for creating new memory entries (PyQt6 version).
"""

from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QShortcut, QKeySequence
from PyQt6.QtWidgets import QApplication

from .database import add_entry


class QuickAddDialog(QDialog):
    """Dialog for quickly adding a new memory entry."""

    def __init__(self, parent=None, on_save_callback: Optional[Callable] = None):
        super().__init__(parent)
        self._on_save_callback = on_save_callback
        self._init_ui()
        self._populate_from_clipboard()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Quick Add Memory")
        self.setModal(True)
        self.setFixedSize(550, 480)

        # Style
        self.setStyleSheet("""
            QDialog {
                background: #FDF6E3;
            }
            QLabel {
                color: #073642;
                font-size: 10pt;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: white;
                color: #073642;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
            }
            QComboBox {
                padding-right: 25px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #073642;
                width: 0;
                height: 0;
                margin-right: 8px;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Title field
        title_label = QLabel("Title:")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_layout.addWidget(title_label)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Enter title (or auto-generated from content)")
        self.title_input.setFont(QFont("Segoe UI", 11))
        main_layout.addWidget(self.title_input)

        # Category field
        category_label = QLabel("Category:")
        category_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_layout.addWidget(category_label)

        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "note",
            "reference",
            "idea",
            "snippet",
            "email",
            "conversation"
        ])
        self.category_combo.setCurrentText("note")
        self.category_combo.setFont(QFont("Segoe UI", 10))
        main_layout.addWidget(self.category_combo)

        # Content field
        content_label = QLabel("Content (paste with Ctrl+V):")
        content_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_layout.addWidget(content_label)

        self.content_text = QTextEdit()
        self.content_text.setPlaceholderText("Enter or paste content here...")
        self.content_text.setFont(QFont("Consolas", 10))
        main_layout.addWidget(self.content_text)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: #D3CBB7; margin: 5px 0;")
        main_layout.addWidget(separator)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #93A1A1;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #657B83;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(100)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #859900;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #719E00;
            }
        """)
        save_btn.clicked.connect(self._save_and_close)
        button_layout.addWidget(save_btn)

        main_layout.addLayout(button_layout)

        # Keyboard shortcuts
        save_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        save_shortcut.activated.connect(self._save_and_close)

        cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        cancel_shortcut.activated.connect(self.reject)

        # Focus on title
        self.title_input.setFocus()

    def _populate_from_clipboard(self):
        """Try to populate content from clipboard."""
        try:
            clipboard = QApplication.clipboard()
            text = clipboard.text()

            if text:
                self.content_text.setPlainText(text)

                # Auto-generate title from first line
                first_line = text.split('\n')[0][:60].strip()
                if first_line:
                    self.title_input.setText(first_line)
        except Exception as e:
            print(f"Could not access clipboard: {e}")

    def _save_and_close(self):
        """Validate and save the entry."""
        title = self.title_input.text().strip()
        content = self.content_text.toPlainText().strip()
        category = self.category_combo.currentText()

        # Validation
        if not content:
            QMessageBox.warning(
                self,
                "Empty Content",
                "Please enter some content."
            )
            return

        if not title:
            title = "Untitled note"

        # Save to database
        try:
            entry_id = add_entry(
                title=title,
                content=content,
                category=category,
                tags="quick-add"
            )

            # Call callback if provided
            if self._on_save_callback:
                self._on_save_callback()

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving",
                f"Failed to save entry: {str(e)}"
            )
