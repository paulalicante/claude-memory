"""
PDF Import dialog for importing PDF files (PyQt6 version).
"""

import os
from typing import Optional, Callable
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QComboBox, QMessageBox,
    QFileDialog, QFrame, QGroupBox, QProgressDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QShortcut, QKeySequence

from .database import add_entry


class PDFImportDialog(QDialog):
    """Dialog for importing PDF files."""

    def __init__(self, parent=None, on_save_callback: Optional[Callable] = None):
        super().__init__(parent)
        self._on_save_callback = on_save_callback
        self._pdf_path = None
        self._extracted_text = ""
        self._select_pdf_file()

    def _select_pdf_file(self):
        """Open file dialog to select PDF."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent(),
            "Import PDF",
            "",
            "PDF Files (*.pdf);;All Files (*.*)"
        )

        if not file_path:
            # User cancelled
            return

        # Check PDF support
        try:
            from .pdf_handler import is_pdf_support_available

            if not is_pdf_support_available():
                QMessageBox.critical(
                    self.parent(),
                    "PDF Support Not Available",
                    "PDF support requires PyMuPDF and Pillow.\n\n"
                    "Install with: pip install PyMuPDF Pillow"
                )
                return
        except Exception as e:
            QMessageBox.critical(
                self.parent(),
                "Error",
                f"Failed to check PDF support: {str(e)}"
            )
            return

        # Import the PDF
        self._import_pdf(file_path)

    def _import_pdf(self, file_path: str):
        """Import the selected PDF file."""
        # Show progress
        progress = QProgressDialog("Importing PDF and extracting text...", None, 0, 0, self.parent())
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        try:
            from .pdf_handler import import_pdf

            stored_path, extracted_text, title = import_pdf(file_path)

            progress.close()

            if stored_path is None:
                QMessageBox.critical(
                    self.parent(),
                    "Import Failed",
                    title  # title contains error message
                )
                return

            # Store the results
            self._pdf_path = stored_path
            self._extracted_text = extracted_text

            # Show save dialog
            self._init_ui(title)

        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self.parent(),
                "Import Error",
                f"Failed to import PDF:\n{str(e)}"
            )

    def _init_ui(self, default_title: str):
        """Initialize the user interface."""
        self.setWindowTitle("Save PDF")
        self.setModal(True)
        self.setFixedSize(600, 500)

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
            QGroupBox {
                color: #073642;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
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
        self.title_input.setText(default_title)
        self.title_input.setFont(QFont("Segoe UI", 11))
        self.title_input.selectAll()
        main_layout.addWidget(self.title_input)

        # Category field
        category_label = QLabel("Category:")
        category_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_layout.addWidget(category_label)

        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "document",
            "reference",
            "research",
            "manual",
            "report"
        ])
        self.category_combo.setCurrentText("document")
        self.category_combo.setFont(QFont("Segoe UI", 10))
        main_layout.addWidget(self.category_combo)

        # Tags field
        tags_label = QLabel("Tags:")
        tags_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_layout.addWidget(tags_label)

        self.tags_input = QLineEdit()
        self.tags_input.setText("pdf")
        self.tags_input.setFont(QFont("Segoe UI", 10))
        main_layout.addWidget(self.tags_input)

        # Preview group
        preview_group = QGroupBox("Extracted Text Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Consolas", 9))

        # Show first 2000 characters
        preview_content = self._extracted_text[:2000]
        if len(self._extracted_text) > 2000:
            preview_content += "..."
        self.preview_text.setPlainText(preview_content)

        preview_layout.addWidget(self.preview_text)
        main_layout.addWidget(preview_group)

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
        save_shortcut = QShortcut(QKeySequence("Return"), self)
        save_shortcut.activated.connect(self._save_and_close)

        cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        cancel_shortcut.activated.connect(self.reject)

        # Focus on title
        self.title_input.setFocus()

        # Show the dialog
        self.exec()

    def _save_and_close(self):
        """Validate and save the PDF entry."""
        title = self.title_input.text().strip()
        category = self.category_combo.currentText()
        tags = self.tags_input.text().strip() or "pdf"

        if not title:
            title = os.path.basename(self._pdf_path)

        # Save to database
        try:
            entry_id = add_entry(
                title=title,
                content=self._extracted_text,
                category=category,
                tags=tags,
                pdf_path=self._pdf_path
            )

            # Call callback if provided
            if self._on_save_callback:
                self._on_save_callback()

            QMessageBox.information(
                self,
                "PDF Imported",
                f"PDF saved as entry #{entry_id}\n\nClick on it to view the formatted PDF."
            )

            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving",
                f"Failed to save entry: {str(e)}"
            )
