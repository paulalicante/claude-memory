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

from . import constants
from .database import search_entries, get_categories, get_entry_by_id, get_recent_entries, delete_entry, add_entry
from .detail_window_pyqt import DetailWindow
from .quick_add_dialog import QuickAddDialog
from .pdf_import_dialog import PDFImportDialog


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

        # Auto-refresh
        self._auto_refresh_timer = None
        self._last_entry_id = 0

        # Detail window
        self._detail_window = DetailWindow()

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

        btn_search = QPushButton("🔍 Search")
        btn_search.clicked.connect(self._do_search)
        layout.addWidget(btn_search)

        btn_add = QPushButton("+ Clipboard")
        btn_add.clicked.connect(self._show_quick_add)
        layout.addWidget(btn_add)

        btn_pdf = QPushButton("📄 Import PDF")
        btn_pdf.clicked.connect(self._import_pdf)
        layout.addWidget(btn_pdf)

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
                border-radius: 6px;
                padding: 15px;
                margin: 8px;
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

        self.results_list.itemDoubleClicked.connect(self._on_double_click)
        self.results_list.itemClicked.connect(self._on_select)
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
            self._results = search_entries(query, category=category)
        else:
            self._results = get_recent_entries(limit=50)

        self._populate_results()

    def _populate_results(self):
        """Populate results list"""
        self.results_list.clear()

        for entry in self._results:
            title = entry.get('title', 'Untitled')
            category = entry.get('category', 'Uncategorized')
            date = entry.get('created_at', '')

            item = QListWidgetItem(f"{title}\n{category} • {date}")
            item.setFont(QFont("Segoe UI", 11))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.results_list.addItem(item)

        self.stats_label.setText(f"{len(self._results)} entries")

    def _on_select(self, item):
        """Handle item selection"""
        self._selected_entry = item.data(Qt.ItemDataRole.UserRole)

    def _on_double_click(self, item):
        """Open detail window on double-click"""
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry:
            self._detail_window.show_entry(entry, on_delete_callback=self._on_entry_deleted)

    def _on_entry_deleted(self, entry):
        """Callback when an entry is deleted from detail window"""
        # Refresh the search results
        self._do_search()

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
