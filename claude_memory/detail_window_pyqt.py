"""
Detail window for viewing memory entries (PyQt6 version).
Shows the full content of a selected memory in a separate window.
"""

import json
from typing import Optional, List, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap, QFont

from . import constants


class CustomTitleBar(QWidget):
    """Custom title bar widget for frameless window"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.dragging = False
        self.drag_position = QPoint()

        self.setFixedHeight(35)
        self.setStyleSheet("background: #EEE8D5; border-bottom: 1px solid #D3CBB7;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # Window title
        self.title_label = QLabel("Detail")
        self.title_label.setStyleSheet("color: #073642; font-weight: bold;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Minimize button
        min_btn = QPushButton("−")
        min_btn.setFixedSize(45, 35)
        min_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #073642;
                border: none;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #D3CBB7;
            }
        """)
        min_btn.clicked.connect(parent.showMinimized)
        layout.addWidget(min_btn)

        # Maximize button
        max_btn = QPushButton("□")
        max_btn.setFixedSize(45, 35)
        max_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #073642;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #D3CBB7;
            }
        """)
        max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(max_btn)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(45, 35)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #073642;
                border: none;
                font-size: 24px;
            }
            QPushButton:hover {
                background: #DC322F;
                color: white;
            }
        """)
        close_btn.clicked.connect(parent.close)
        layout.addWidget(close_btn)

    def _toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.parent.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False


class DetailWindow(QWidget):
    """Separate window for viewing memory entry details."""

    def __init__(self):
        super().__init__()
        self._current_entry: Optional[dict] = None
        self._on_delete_callback: Optional[Callable] = None
        self._on_close_callback: Optional[Callable] = None

        # PDF viewer storage
        self._pdf_images: List[QPixmap] = []

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        # Frameless window with custom title bar
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.setGeometry(100, 100, 800, 700)
        self.setStyleSheet("background: #FDF6E3;")

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Header with metadata and delete button
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: #EEE8D5;
                border-bottom: 1px solid #D3CBB7;
                padding: 10px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)

        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #657B83; font-size: 10pt;")
        header_layout.addWidget(self.meta_label)

        header_layout.addStretch()

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: #DC322F;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #CB4B16;
            }
        """)
        self.delete_btn.clicked.connect(self._delete_current)
        header_layout.addWidget(self.delete_btn)

        main_layout.addWidget(header_frame)

        # Content area with scroll
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: #FDF6E3;
            }
            QScrollBar:vertical {
                background: #EEE8D5;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #93A1A1;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #657B83;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Content widget (will be replaced based on content type)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)

        # Text viewer (default)
        self.text_viewer = QTextEdit()
        self.text_viewer.setReadOnly(True)
        self.text_viewer.setStyleSheet("""
            QTextEdit {
                background: #FDF6E3;
                color: #073642;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                padding: 15px;
                font-size: 11pt;
                font-family: 'Segoe UI';
            }
        """)
        self.content_layout.addWidget(self.text_viewer)

        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)

    def show_entry(self, entry: dict, on_delete_callback: Optional[Callable] = None,
                   on_close_callback: Optional[Callable] = None, parent_window=None):
        """Show the detail window with the given entry."""
        self._current_entry = entry
        self._on_delete_callback = on_delete_callback
        self._on_close_callback = on_close_callback

        # Position near parent window if provided
        if parent_window:
            parent_geo = parent_window.geometry()
            # Position to the right of parent with some offset
            x = parent_geo.x() + parent_geo.width() + 20
            y = parent_geo.y()
            self.move(x, y)

        self._display_entry(entry)
        self.show()
        self.raise_()
        self.activateWindow()

    def _display_entry(self, entry: dict):
        """Display the entry content in the appropriate viewer."""
        # Update window title
        title = entry.get('title', 'Detail')
        self.title_bar.title_label.setText(f"{constants.APP_NAME} - {title}")

        # Update metadata
        category = entry.get("category", "None")
        tags = entry.get("tags", "")
        date = entry.get("created_date", "Unknown")
        self.meta_label.setText(f"Category: {category} | Tags: {tags} | Created: {date}")

        # Check content type and display accordingly
        if self._is_pdf_entry(entry):
            self._show_pdf_viewer(entry)
        elif self._is_html_entry(entry):
            self._show_html_viewer(entry)
        else:
            self._show_text_detail(entry)

    def _is_pdf_entry(self, entry: dict) -> bool:
        """Check if entry has PDF data."""
        try:
            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            return metadata.get("content_type") == "pdf"
        except:
            return False

    def _is_html_entry(self, entry: dict) -> bool:
        """Check if entry has HTML email data."""
        try:
            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            return metadata.get("content_type") == "html" and "html_content" in metadata
        except:
            return False

    def _show_text_detail(self, entry: dict):
        """Show text content in the detail pane."""
        # Clear content layout
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Re-create text viewer
        self.text_viewer = QTextEdit()
        self.text_viewer.setReadOnly(True)
        self.text_viewer.setStyleSheet("""
            QTextEdit {
                background: #FDF6E3;
                color: #073642;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                padding: 15px;
                font-size: 11pt;
                font-family: 'Segoe UI';
            }
        """)
        self.text_viewer.setPlainText(entry.get("content", ""))
        self.content_layout.addWidget(self.text_viewer)

    def _show_pdf_viewer(self, entry: dict):
        """Show PDF content in the detail pane."""
        try:
            from .pdf_handler import is_pdf_support_available, render_pdf_to_images
            import os

            if not is_pdf_support_available():
                self._show_text_detail(entry)
                return

            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            pdf_filename = metadata.get("pdf_filename")

            if not pdf_filename:
                self._show_text_detail(entry)
                return

            pdf_path = os.path.join("pdfs", pdf_filename)
            if not os.path.exists(pdf_path):
                self._show_text_detail(entry)
                return

            # Clear content layout
            while self.content_layout.count():
                child = self.content_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Clear previous images
            self._pdf_images.clear()

            # Render PDF pages
            page_images = render_pdf_to_images(pdf_path, max_width=750)

            for i, pil_image in enumerate(page_images):
                # Convert PIL image to QPixmap
                from PIL.ImageQt import ImageQt
                qimage = ImageQt(pil_image)
                pixmap = QPixmap.fromImage(qimage)
                self._pdf_images.append(pixmap)

                # Create label for image
                label = QLabel()
                label.setPixmap(pixmap)
                label.setStyleSheet("background: #FDF6E3; padding: 10px; border: 1px solid #D3CBB7; border-radius: 6px;")
                self.content_layout.addWidget(label)

                if i < len(page_images) - 1:
                    # Add separator between pages
                    sep = QFrame()
                    sep.setFrameShape(QFrame.Shape.HLine)
                    sep.setStyleSheet("background: #D3CBB7; margin: 10px 0;")
                    self.content_layout.addWidget(sep)

            self.content_layout.addStretch()

        except Exception as e:
            print(f"Error showing PDF: {e}")
            self._show_text_detail(entry)

    def _show_html_viewer(self, entry: dict):
        """Show HTML email content in the detail pane."""
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView

            metadata_str = entry.get("source_conversation", "{}")
            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            html_content = metadata.get("html_content", "")

            if not html_content:
                self._show_text_detail(entry)
                return

            # Clear content layout
            while self.content_layout.count():
                child = self.content_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Create web view
            web_view = QWebEngineView()

            sender = metadata.get('sender', 'Unknown')
            subject = metadata.get('subject', 'No subject')

            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        font-family: 'Segoe UI', Arial, sans-serif;
                        margin: 15px;
                        background: #FDF6E3;
                    }}
                    .email-header {{
                        background: #f5f5f5;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                        border-left: 4px solid #268BD2;
                    }}
                    .email-header h3 {{
                        margin: 0 0 10px 0;
                        color: #333;
                    }}
                    .email-header p {{
                        margin: 5px 0;
                        color: #666;
                    }}
                    .email-body {{
                        line-height: 1.6;
                    }}
                </style>
            </head>
            <body>
                <div class="email-header">
                    <h3>{entry.get('title', 'Email')}</h3>
                    <p><strong>From:</strong> {sender}</p>
                    <p><strong>Subject:</strong> {subject}</p>
                </div>
                <div class="email-body">
                    {html_content}
                </div>
            </body>
            </html>
            """

            web_view.setHtml(full_html)
            self.content_layout.addWidget(web_view)

        except ImportError:
            # QtWebEngine not available, fall back to text
            print("QtWebEngine not available, showing text instead")
            self._show_text_detail(entry)
        except Exception as e:
            print(f"Error rendering HTML: {e}")
            self._show_text_detail(entry)

    def _delete_current(self):
        """Delete the currently displayed entry."""
        if self._current_entry and self._on_delete_callback:
            self._on_delete_callback(self._current_entry)
            self.close()

    def closeEvent(self, event):
        """Handle window close event."""
        if self._on_close_callback:
            self._on_close_callback()
        event.accept()
