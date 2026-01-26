"""
PyQt6-based search window with Solarized Light custom title bar.
Drop-in replacement for tkinter search_window.py
"""

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QLabel, QPushButton, QLineEdit,
                              QTextEdit, QListWidget, QListWidgetItem, QFrame,
                              QComboBox, QCheckBox, QSplitter, QMessageBox, QScrollArea)
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QFont, QMouseEvent
from typing import Optional, List
import sys
import html
import re

from . import constants
from .database import search_entries, get_categories, get_entry_by_id, get_recent_entries, delete_entry, add_entry, unified_search
from .detail_window_pyqt import DetailWindow
from .quick_add_dialog import QuickAddDialog
from .pdf_import_dialog import PDFImportDialog


class HoverPreview(QLabel):
    """Custom hover preview widget with fixed size"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(300, 200)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setTextFormat(Qt.TextFormat.RichText)  # Enable HTML formatting
        self.setStyleSheet("""
            QLabel {
                background: #FDF6E3;
                color: #073642;
                border: 2px solid #268BD2;
                border-radius: 6px;
                padding: 12px;
                font-size: 10pt;
                font-family: 'Segoe UI';
            }
        """)
        self.hide()


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
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(10)

        # App title
        self.title = QLabel(constants.APP_NAME)
        self.title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.title.setStyleSheet("color: #073642; background: transparent;")
        layout.addWidget(self.title)

        layout.addStretch()

        # Window control buttons
        btn_style = """
            QPushButton {
                background: transparent;
                border: none;
                color: #073642;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                min-width: 35px;
                max-width: 35px;
                min-height: 30px;
                max-height: 30px;
            }
            QPushButton:hover {
                background: #D3CBB7;
            }
        """

        close_hover = """
            QPushButton {
                background: transparent;
                border: none;
                color: #073642;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                min-width: 35px;
                max-width: 35px;
                min-height: 30px;
                max-height: 30px;
            }
            QPushButton:hover {
                background: #DC2626;
                color: white;
            }
        """

        # Minimize
        self.btn_minimize = QPushButton("−")
        self.btn_minimize.setStyleSheet(btn_style)
        self.btn_minimize.clicked.connect(self.parent.showMinimized)
        layout.addWidget(self.btn_minimize)

        # Maximize
        self.btn_maximize = QPushButton("□")
        self.btn_maximize.setStyleSheet(btn_style)
        self.btn_maximize.clicked.connect(self.toggle_maximize)
        layout.addWidget(self.btn_maximize)

        # Close
        self.btn_close = QPushButton("×")
        self.btn_close.setStyleSheet(close_hover)
        self.btn_close.clicked.connect(self.parent.hide)
        layout.addWidget(self.btn_close)

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.btn_maximize.setText("□")
        else:
            self.parent.showMaximized()
            self.btn_maximize.setText("❐")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.parent.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging = False

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.toggle_maximize()


class SearchWindow(QMainWindow):
    """PyQt6 search window with Solarized custom title bar"""

    def __init__(self, on_chat: callable = None, chat_window=None):
        super().__init__()

        self._on_chat = on_chat
        self._chat_window = chat_window
        self._results: List[dict] = []
        self._selected_entry: Optional[dict] = None
        self._displayed_entry_id: Optional[int] = None  # Track which entry is currently shown in detail window

        # Auto-refresh
        self._auto_refresh_timer = None
        self._last_entry_id = 0

        # Detail window
        self._detail_window = DetailWindow()

        # Hover preview
        self._hover_preview = HoverPreview(None)  # No parent - independent window

        # Multi-select state
        self._multi_select_mode = False
        self._check_widgets = []  # List of (checkbox, entry, widget) tuples

        # Frameless window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 50, 900, 700)

        # Main container
        container = QWidget()
        container.setStyleSheet("background: #FDF6E3;")
        self.setCentralWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)

        # Status bar styling
        self.setStyleSheet("""
            QStatusBar {
                background: #073642;
                color: #93A1A1;
                border-top: 1px solid #002B36;
            }
        """)

        # Content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._create_ui(content_layout)

        main_layout.addWidget(content_widget)

        # Status bar
        statusbar = self.statusBar()
        statusbar.showMessage("Ready")

        # Auto-refresh placeholder files on startup (run after UI is shown)
        QTimer.singleShot(500, self._auto_refresh_placeholders)

    def _auto_refresh_placeholders(self):
        """Auto-refresh any files with placeholder content."""
        from .file_indexer import auto_refresh_placeholder_files
        try:
            count = auto_refresh_placeholder_files()
            if count > 0:
                self.statusBar().showMessage(f"Auto-refreshed {count} files", 3000)
        except Exception as e:
            print(f"Error during auto-refresh: {e}")

    def _create_ui(self, parent_layout):
        """Create main UI"""
        ui_widget = QWidget()
        main_layout = QHBoxLayout(ui_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sidebar
        sidebar = self._create_sidebar()
        splitter.addWidget(sidebar)

        # Results area
        results = self._create_results_area()
        splitter.addWidget(results)

        splitter.setSizes([250, 650])
        main_layout.addWidget(splitter)

        parent_layout.addWidget(ui_widget)

    def _create_sidebar(self):
        """Create sidebar with controls"""
        sidebar = QFrame()
        sidebar.setStyleSheet("""
            QFrame {
                background: #073642;
                border-right: 1px solid #002B36;
            }
            QLabel {
                color: #93A1A1;
                background: transparent;
            }
            QPushButton {
                background: #586E75;
                color: #FDF6E3;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                text-align: left;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #657B83;
            }
            QPushButton:pressed {
                background: #268BD2;
            }
            QLineEdit {
                background: #586E75;
                color: #FDF6E3;
                border: 1px solid #657B83;
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit:focus {
                border: 2px solid #268BD2;
            }
            QComboBox {
                background: #586E75;
                color: #FDF6E3;
                border: 1px solid #657B83;
                border-radius: 6px;
                padding: 8px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #FDF6E3;
                width: 0;
                height: 0;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #FDF6E3;
                color: #073642;
                selection-background-color: #268BD2;
                selection-color: #FDF6E3;
                border: 1px solid #D3CBB7;
            }
        """)
        sidebar.setMaximumWidth(300)
        sidebar.setMinimumWidth(200)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel("Claude Memory")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #FDF6E3;")
        layout.addWidget(title)

        # Search
        layout.addSpacing(10)
        search_label = QLabel("Search:")
        search_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search terms...")
        self.search_input.setClearButtonEnabled(True)  # Add X clear button
        self.search_input.returnPressed.connect(self._do_search)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_input)

        # Category filter
        layout.addSpacing(10)
        cat_label = QLabel("Category:")
        cat_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        layout.addWidget(cat_label)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["All"])
        self.category_combo.currentTextChanged.connect(self._do_search)
        layout.addWidget(self.category_combo)

        # Multi-select checkbox
        layout.addSpacing(20)
        self.multi_select_checkbox = QCheckBox("Multi-Select Mode")
        self.multi_select_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FDF6E3;
                background: transparent;
                font-size: 11px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #657B83;
                border-radius: 3px;
                background: #586E75;
            }
            QCheckBox::indicator:checked {
                background: #268BD2;
                border-color: #268BD2;
            }
            QCheckBox::indicator:hover {
                border-color: #93A1A1;
            }
        """)
        self.multi_select_checkbox.stateChanged.connect(self._toggle_multi_select)
        layout.addWidget(self.multi_select_checkbox)

        # Actions
        layout.addSpacing(10)
        actions_label = QLabel("Actions")
        actions_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        layout.addWidget(actions_label)

        btn_add = QPushButton("+ Clipboard")
        btn_add.clicked.connect(self._show_quick_add)
        layout.addWidget(btn_add)

        btn_pdf = QPushButton("📄 Import PDF")
        btn_pdf.clicked.connect(self._import_pdf)
        layout.addWidget(btn_pdf)

        btn_files = QPushButton("📁 File Discovery")
        btn_files.clicked.connect(self._launch_file_discovery)
        layout.addWidget(btn_files)

        btn_save_convo = QPushButton("💬 Save Conversation")
        btn_save_convo.clicked.connect(self._save_conversation)
        layout.addWidget(btn_save_convo)

        btn_tag_faces = QPushButton("👤 Tag Faces")
        btn_tag_faces.clicked.connect(self._launch_face_tagging)
        layout.addWidget(btn_tag_faces)

        # Multi-select buttons (hidden initially)
        self.btn_delete_multi = QPushButton("🗑 Delete Selected")
        self.btn_delete_multi.clicked.connect(self._delete_multiple)
        self.btn_delete_multi.setVisible(False)
        layout.addWidget(self.btn_delete_multi)

        self.btn_remove_dupes = QPushButton("🔗 Remove Duplicates")
        self.btn_remove_dupes.clicked.connect(self._remove_duplicates)
        self.btn_remove_dupes.setVisible(False)
        layout.addWidget(self.btn_remove_dupes)

        # Single-select buttons
        self.btn_delete = QPushButton("🗑 Delete Selected")
        self.btn_delete.clicked.connect(self._delete_selected)
        layout.addWidget(self.btn_delete)

        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self._refresh)
        layout.addWidget(btn_refresh)

        layout.addStretch()

        # Stats
        self.stats_label = QLabel("0 entries")
        self.stats_label.setStyleSheet("color: #586E75; font-size: 11px;")
        layout.addWidget(self.stats_label)

        return sidebar

    def _create_results_area(self):
        """Create results list area"""
        center = QFrame()
        center.setStyleSheet("background: #EEE8D5;")

        layout = QVBoxLayout(center)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Results list
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("""
            QListWidget {
                background: #EEE8D5;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: #FDF6E3;
                border: 1px solid #D3CBB7;
                border-radius: 4px;
                padding: 8px 12px;
                margin: 4px;
                color: #073642;
            }
            QListWidget::item:selected {
                background: #268BD2;
                border: 2px solid #268BD2;
                color: #FDF6E3;
            }
            QListWidget::item:hover {
                background: #F5EDDA;
                border: 1px solid #93A1A1;
            }
        """)

        self.results_list.itemClicked.connect(self._on_item_click)
        self.results_list.setMouseTracking(True)
        self.results_list.itemEntered.connect(self._on_item_hover)
        self.results_list.installEventFilter(self)
        layout.addWidget(self.results_list)

        # Checkbox scroll area (for multi-select mode)
        self.checkbox_scroll = QScrollArea()
        self.checkbox_scroll.setWidgetResizable(True)
        self.checkbox_scroll.setStyleSheet("""
            QScrollArea {
                background: #EEE8D5;
                border: none;
            }
        """)

        # Container for checkboxes
        self.checkbox_container = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_container)
        self.checkbox_layout.setContentsMargins(10, 10, 10, 10)
        self.checkbox_layout.setSpacing(5)
        self.checkbox_layout.addStretch()

        self.checkbox_scroll.setWidget(self.checkbox_container)
        layout.addWidget(self.checkbox_scroll)
        self.checkbox_scroll.setVisible(False)  # Hidden by default

        # Multi-select notice
        self.multi_select_notice = QLabel("⚠ Multi-select mode is active")
        self.multi_select_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.multi_select_notice.setStyleSheet("""
            QLabel {
                background: #FFF3E0;
                color: #FF6600;
                font-size: 12pt;
                font-weight: bold;
                padding: 20px;
                border: 2px solid #FFB74D;
                border-radius: 6px;
                margin: 10px;
            }
        """)
        layout.addWidget(self.multi_select_notice)
        self.multi_select_notice.setVisible(False)  # Hidden by default

        return center

    def _on_search_text_changed(self, text):
        """Handle search text changes - auto-search when cleared"""
        if not text:
            # When search is cleared (X button clicked), show all recent entries
            self._do_search()

    def _do_search(self):
        """Perform search"""
        query = self.search_input.text()
        category = self.category_combo.currentText()
        if category == "All":
            category = None

        if query:
            # Use unified search to include both memories and files
            self._results = unified_search(query, category=category)
        else:
            # No query - show recent entries, optionally filtered by category
            if category:
                self._results = search_entries("", category=category)
                # Add result_type to recent entries
                for entry in self._results:
                    entry['result_type'] = 'memory'
            else:
                self._results = get_recent_entries(limit=50)
                # Add result_type to recent entries
                for entry in self._results:
                    entry['result_type'] = 'memory'

        self._populate_results()

    def _populate_results(self):
        """Populate results list"""
        self.results_list.clear()

        for entry in self._results:
            result_type = entry.get('result_type', 'memory')
            title = entry.get('title', 'Untitled')
            category = entry.get('category', 'Uncategorized')
            date = entry.get('created_at', entry.get('date', ''))

            # Different icon based on result type
            icon = "📝" if result_type == "memory" else "📄"
            item = QListWidgetItem(f"{icon} {title} • {category} • {date}")
            item.setFont(QFont("Segoe UI", 10))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.results_list.addItem(item)

        # Count memories and files separately
        memory_count = sum(1 for e in self._results if e.get('result_type') == 'memory')
        file_count = len(self._results) - memory_count
        if file_count > 0:
            self.stats_label.setText(f"{memory_count} memories, {file_count} files")
        else:
            self.stats_label.setText(f"{len(self._results)} entries")

    def _on_item_click(self, item):
        """Open detail window on single click (toggle if same entry clicked again)"""
        # Hide hover preview when clicking
        self._hover_preview.hide()

        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry:
            result_type = entry.get('result_type', 'memory')

            # Handle file results differently
            if result_type == 'file':
                self._show_file_actions(entry)
            else:
                # Memory entry - show in detail window
                entry_id = entry.get('id')
                self._selected_entry = entry

                # Toggle: if clicking the same entry that's already displayed, close the window
                if self._displayed_entry_id == entry_id and self._detail_window.isVisible():
                    self._detail_window.hide()
                    self._displayed_entry_id = None
                else:
                    # Show the detail window positioned next to this window
                    self._detail_window.show_entry(entry,
                                                   on_delete_callback=self._on_entry_deleted,
                                                   on_close_callback=self._on_detail_closed,
                                                   parent_window=self)
                    self._displayed_entry_id = entry_id

        # Clear selection so item returns to normal appearance
        self.results_list.clearSelection()

    def _on_entry_deleted(self, entry):
        """Callback when an entry is deleted from detail window"""
        # Clear the displayed entry tracking
        self._displayed_entry_id = None
        # Refresh the search results
        self._do_search()

    def _on_detail_closed(self):
        """Callback when detail window is closed"""
        # Clear the displayed entry tracking
        self._displayed_entry_id = None

    def eventFilter(self, obj, event):
        """Handle events for the results list - hide preview on mouse leave"""
        if obj == self.results_list and event.type() == event.Type.Leave:
            self._hover_preview.hide()
        return super().eventFilter(obj, event)

    def _on_item_hover(self, item):
        """Show custom preview when hovering over an item"""
        if not item:
            self._hover_preview.hide()
            return

        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            self._hover_preview.hide()
            return

        # Get content and format for fixed-size preview
        content = entry.get('content', '')

        # Check if there's an active search query
        search_query = self.search_input.text().strip()

        if search_query:
            # Find the search term in the content (case-insensitive)
            content_lower = content.lower()
            query_lower = search_query.lower()
            match_pos = content_lower.find(query_lower)

            if match_pos != -1:
                # Extract context around the match (150 chars before and after)
                context_size = 150
                start = max(0, match_pos - context_size)
                end = min(len(content), match_pos + len(search_query) + context_size)

                preview_text = content[start:end]

                # Add ellipsis if we're not at the start/end
                if start > 0:
                    preview_text = '...' + preview_text
                if end < len(content):
                    preview_text = preview_text + '...'
            else:
                # Fallback to beginning if search term not found
                preview_text = content[:400]
                if len(content) > 400:
                    preview_text += '...'
        else:
            # No search query - show from beginning
            preview_text = content[:400]
            if len(content) > 400:
                preview_text += '...'

        # Update preview text with highlighting if there's a search query
        if search_query:
            # Escape HTML characters in the preview text
            escaped_text = html.escape(preview_text)

            # Highlight all occurrences of the search term (case-insensitive)
            # Use a case-insensitive regex replacement
            def highlight_match(match):
                return f'<span style="background-color: #B58900; color: #FDF6E3; font-weight: bold; padding: 2px 4px; border-radius: 3px;">{match.group(0)}</span>'

            highlighted_text = re.sub(
                re.escape(search_query),
                highlight_match,
                escaped_text,
                flags=re.IGNORECASE
            )

            # Wrap in HTML with proper styling
            formatted_text = f'<div style="color: #073642; font-family: Segoe UI; font-size: 10pt;">{highlighted_text}</div>'
            self._hover_preview.setText(formatted_text)
        else:
            # No search query - just escape HTML and display plain
            escaped_text = html.escape(preview_text)
            formatted_text = f'<div style="color: #073642; font-family: Segoe UI; font-size: 10pt;">{escaped_text}</div>'
            self._hover_preview.setText(formatted_text)

        # Position preview near cursor using global coordinates
        from PyQt6.QtGui import QGuiApplication
        cursor_pos = self.cursor().pos()  # Global position
        screen = QGuiApplication.screenAt(cursor_pos)
        if screen:
            screen_geometry = screen.geometry()
        else:
            # Fallback to primary screen
            screen_geometry = QGuiApplication.primaryScreen().geometry()

        preview_x = cursor_pos.x() + 20
        preview_y = cursor_pos.y() + 20

        # Make sure it doesn't go off screen (using screen boundaries)
        if preview_x + 300 > screen_geometry.right():
            preview_x = cursor_pos.x() - 320

        if preview_y + 200 > screen_geometry.bottom():
            preview_y = cursor_pos.y() - 220

        self._hover_preview.move(preview_x, preview_y)
        self._hover_preview.show()
        self._hover_preview.raise_()

    def _delete_selected(self):
        """Delete selected entry"""
        if not self._selected_entry:
            QMessageBox.warning(self, "No Selection", "Please select an entry to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete entry '{self._selected_entry.get('title', 'Untitled')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_entry(self._selected_entry['id'])
            self._do_search()

    def _refresh(self):
        """Refresh results"""
        self._do_search()

    def _show_quick_add(self):
        """Show quick add dialog"""
        dialog = QuickAddDialog(self, on_save_callback=self._do_search)
        dialog.exec()

    def _import_pdf(self):
        """Import PDF"""
        PDFImportDialog(self, on_save_callback=self._do_search)

    def _launch_file_discovery(self):
        """Launch the file discovery dialog"""
        from .discovery_dialog import DiscoveryDialog
        dialog = DiscoveryDialog(self)
        result = dialog.exec()
        # Refresh results if files were indexed
        if result:
            self._do_search()

    def _launch_face_tagging(self):
        """Launch the face tagging dialog"""
        from .face_tagging_dialog import FaceTaggingDialog
        dialog = FaceTaggingDialog(self)
        dialog.exec()
        # Refresh results after tagging
        self._do_search()

    def _show_file_actions(self, file_entry):
        """Show action buttons for a file result"""
        file_path = file_entry.get('file_path', '')
        file_name = file_entry.get('file_name', 'Unknown')

        msg = QMessageBox(self)
        msg.setWindowTitle("File Actions")
        msg.setText(f"📄 {file_name}")
        msg.setInformativeText(f"Path: {file_path}\n\nWhat would you like to do?")

        open_btn = msg.addButton("Open File", QMessageBox.ButtonRole.ActionRole)
        import_btn = msg.addButton("Import to Memory", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

        msg.exec()

        if msg.clickedButton() == open_btn:
            self._open_file(file_path)
        elif msg.clickedButton() == import_btn:
            self._import_file_to_memory(file_entry)

    def _open_file(self, file_path):
        """Open file in default application"""
        import os
        import subprocess
        import platform

        try:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")

    def _import_file_to_memory(self, file_entry):
        """Import a file as a memory entry"""
        file_path = file_entry.get('file_path', '')
        file_name = file_entry.get('file_name', 'Unknown')
        content_preview = file_entry.get('content_preview', '')
        file_type = file_entry.get('file_type', '')

        # Create memory entry with file info
        title = f"[File] {file_name}"
        content = f"File: {file_path}\n\nContent Preview:\n{content_preview}"

        try:
            add_entry(title=title, content=content, category="File", tags=file_type)
            QMessageBox.information(self, "Success", f"File imported to memory:\n{file_name}")
            self._do_search()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import file:\n{str(e)}")

    def _save_conversation(self):
        """Save current Claude Code conversation to memory"""
        import json
        import os
        from pathlib import Path
        from datetime import datetime

        try:
            # Find the most recent conversation file in .claude/projects
            home = Path.home()
            claude_dir = home / '.claude' / 'projects'

            if not claude_dir.exists():
                QMessageBox.warning(self, "Not Found", "No Claude Code conversations found.")
                return

            # Get current working directory to find the right project folder
            cwd = Path(os.getcwd()).resolve()

            # Find all project folders
            project_folders = [f for f in claude_dir.iterdir() if f.is_dir()]

            # Find most recent .jsonl file across all projects
            latest_file = None
            latest_time = 0

            for project_folder in project_folders:
                jsonl_files = list(project_folder.glob('*.jsonl'))
                for file in jsonl_files:
                    mtime = file.stat().st_mtime
                    if mtime > latest_time:
                        latest_time = mtime
                        latest_file = file

            if not latest_file:
                QMessageBox.warning(self, "Not Found", "No conversation transcript found.")
                return

            # Read and parse the conversation
            messages = []
            with open(latest_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        msg = json.loads(line)
                        messages.append(msg)

            # Format the conversation
            conversation_text = []
            for msg in messages:
                role = msg.get('role', '').upper()
                content = msg.get('content', '')

                # Handle different content types
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                    content = '\n'.join(text_parts)

                if content.strip():
                    conversation_text.append(f"[{role}]\n{content}\n")

            full_conversation = '\n'.join(conversation_text)

            # Create title with date
            date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            title = f"Claude Conversation - {date_str}"

            # Save to database
            add_entry(
                title=title,
                content=full_conversation,
                category="Conversation",
                tags="claude,ai,chat"
            )

            QMessageBox.information(
                self,
                "Saved",
                f"Conversation saved to memory!\n\nTitle: {title}\nMessages: {len(messages)}"
            )
            self._do_search()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save conversation:\n{str(e)}")

    def _toggle_multi_select(self):
        """Toggle between single and multi-select mode"""
        self._multi_select_mode = self.multi_select_checkbox.isChecked()

        if self._multi_select_mode:
            # Enable multi-select
            self.results_list.setVisible(False)
            self.checkbox_scroll.setVisible(True)
            self.multi_select_notice.setVisible(True)

            # Show multi-select buttons, hide single-select button
            self.btn_delete_multi.setVisible(True)
            self.btn_remove_dupes.setVisible(True)
            self.btn_delete.setVisible(False)

            # Populate checkboxes
            self._populate_checkboxes()
        else:
            # Disable multi-select
            self.results_list.setVisible(True)
            self.checkbox_scroll.setVisible(False)
            self.multi_select_notice.setVisible(False)

            # Hide multi-select buttons, show single-select button
            self.btn_delete_multi.setVisible(False)
            self.btn_remove_dupes.setVisible(False)
            self.btn_delete.setVisible(True)

            # Clear checkboxes
            self._check_widgets.clear()

    def _populate_checkboxes(self):
        """Populate the checkbox view with current results"""
        # Clear existing checkboxes
        while self.checkbox_layout.count() > 1:  # Keep the stretch
            child = self.checkbox_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._check_widgets.clear()

        # Create checkbox for each result
        for i, entry in enumerate(self._results):
            # Create frame for this row
            row_frame = QFrame()
            row_frame.setStyleSheet(f"""
                QFrame {{
                    background: {'#FDF6E3' if i % 2 == 0 else '#EEE8D5'};
                    border: 1px solid #D3CBB7;
                    border-radius: 4px;
                    padding: 8px;
                }}
                QFrame:hover {{
                    background: #F5EDDA;
                    border: 1px solid #93A1A1;
                }}
            """)

            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(5, 5, 5, 5)

            # Checkbox
            checkbox = QCheckBox()
            checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 20px;
                    height: 20px;
                    border: 2px solid #657B83;
                    border-radius: 3px;
                    background: white;
                }
                QCheckBox::indicator:checked {
                    background: #268BD2;
                    border-color: #268BD2;
                }
            """)
            row_layout.addWidget(checkbox)

            # Entry label - clickable to view
            title = entry.get('title', 'Untitled')
            category = entry.get('category', 'Uncategorized')
            date = entry.get('created_at', '')

            label = QLabel(f"{title}\n{category} • {date}")
            label.setStyleSheet("color: #073642; font-size: 11pt; background: transparent; border: none;")
            label.setWordWrap(True)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.mousePressEvent = lambda e, ent=entry: self._on_checkbox_label_click(ent)
            row_layout.addWidget(label, 1)

            self.checkbox_layout.insertWidget(self.checkbox_layout.count() - 1, row_frame)
            self._check_widgets.append((checkbox, entry, row_frame))

    def _on_checkbox_label_click(self, entry):
        """Handle click on checkbox label to view entry"""
        self._detail_window.show_entry(entry, on_delete_callback=self._on_entry_deleted)

    def _get_checked_entries(self):
        """Get list of checked entries"""
        return [entry for checkbox, entry, _ in self._check_widgets if checkbox.isChecked()]

    def _delete_multiple(self):
        """Delete all checked entries"""
        checked = self._get_checked_entries()

        if not checked:
            QMessageBox.warning(self, "No Selection", "Please select entries to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(checked)} selected entries?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for entry in checked:
                delete_entry(entry['id'])
            self._do_search()

    def _remove_duplicates(self):
        """Merge duplicate entries line-by-line"""
        checked = self._get_checked_entries()

        if len(checked) < 2:
            QMessageBox.warning(
                self,
                "Insufficient Selection",
                "Please select at least 2 duplicate entries to merge."
            )
            return

        # Confirm merge
        titles = [e.get('title', 'Untitled') for e in checked]
        reply = QMessageBox.question(
            self,
            "Confirm Merge",
            f"Merge {len(checked)} entries?\n\n" + "\n".join(f"• {t}" for t in titles[:5]) +
            (f"\n...and {len(titles) - 5} more" if len(titles) > 5 else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Merge content line-by-line, keeping only unique lines
        all_lines = []
        for entry in checked:
            content = entry.get('content', '')
            lines = content.split('\n')
            all_lines.extend(lines)

        # Remove duplicates while preserving order
        seen = set()
        unique_lines = []
        for line in all_lines:
            line_stripped = line.strip()
            if line_stripped and line_stripped not in seen:
                seen.add(line_stripped)
                unique_lines.append(line)

        merged_content = '\n'.join(unique_lines)

        # Create new merged entry
        merged_title = f"[Merged] {checked[0].get('title', 'Untitled')}"
        merged_category = checked[0].get('category', 'note')

        add_entry(
            title=merged_title,
            content=merged_content,
            category=merged_category,
            tags="merged"
        )

        # Delete original entries
        for entry in checked:
            delete_entry(entry['id'])

        QMessageBox.information(
            self,
            "Merge Complete",
            f"Merged {len(checked)} entries into 1 entry with {len(unique_lines)} unique lines."
        )

        self._do_search()

    def _start_auto_refresh(self):
        """Start auto-refresh timer to check for new entries"""
        # Initialize last entry ID
        try:
            recent = get_recent_entries(limit=1)
            if recent:
                self._last_entry_id = recent[0]['id']
        except Exception:
            pass

        # Start timer (check every 2 seconds)
        if not self._auto_refresh_timer:
            self._auto_refresh_timer = QTimer()
            self._auto_refresh_timer.timeout.connect(self._check_for_updates)
            self._auto_refresh_timer.start(2000)  # 2000ms = 2 seconds

    def _stop_auto_refresh(self):
        """Stop auto-refresh timer"""
        if self._auto_refresh_timer:
            self._auto_refresh_timer.stop()

    def _check_for_updates(self):
        """Check if new entries exist and refresh if needed"""
        try:
            # Get the most recent entry
            recent = get_recent_entries(limit=1)
            if recent and recent[0]['id'] > self._last_entry_id:
                # New entry detected - refresh
                self._last_entry_id = recent[0]['id']
                self._do_search()
        except Exception as e:
            print(f"Error checking for updates: {e}")

    def show(self):
        """Show window"""
        super().show()
        self._refresh_categories()
        self._do_search()
        self._start_auto_refresh()

    def hide(self):
        """Hide window"""
        super().hide()

    def toggle(self):
        """Toggle visibility"""
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def _refresh_categories(self):
        """Refresh category dropdown"""
        current = self.category_combo.currentText()
        self.category_combo.clear()
        self.category_combo.addItem("All")

        categories = get_categories()
        for cat in categories:
            if cat:
                self.category_combo.addItem(cat)

        # Restore selection
        index = self.category_combo.findText(current)
        if index >= 0:
            self.category_combo.setCurrentIndex(index)
