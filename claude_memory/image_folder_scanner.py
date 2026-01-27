"""
Image Folder Scanner for Claude Memory (PyQt6 version).
Scans entire PC including Google Drive to find folders with images.
"""

import os
from pathlib import Path
from typing import Dict, List
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar,
    QMessageBox, QApplication, QFrame, QHeaderView, QCheckBox,
    QComboBox, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush


class ImageScanWorker(QThread):
    """Background thread for scanning system for image folders."""
    progress = pyqtSignal(str, int)  # (current_path, total_folders_found)
    finished = pyqtSignal(dict)  # {folder_path: {'count': int, 'size': int}}
    error = pyqtSignal(str)

    def __init__(self, drives: List[str]):
        super().__init__()
        self.drives = drives
        self._is_cancelled = False
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic'}

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            folder_stats = {}  # {folder_path: {'count': int, 'size': int, 'files': []}}

            for drive in self.drives:
                if self._is_cancelled:
                    return

                self._scan_drive(drive, folder_stats)

            # Convert to simple dict for result
            result = {
                path: {'count': stats['count'], 'size': stats['size']}
                for path, stats in folder_stats.items()
            }

            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))

    def _scan_drive(self, drive_path: str, folder_stats: dict):
        """Scan a drive for image folders."""
        try:
            for root, dirs, files in os.walk(drive_path):
                if self._is_cancelled:
                    return

                # Skip system folders
                if any(skip in root.lower() for skip in [
                    'windows', 'program files', 'appdata', '$recycle.bin',
                    'system volume information', 'perflogs', 'programdata'
                ]):
                    dirs.clear()  # Don't descend into subdirs
                    continue

                # Check if this folder has images
                image_files = [f for f in files if Path(f).suffix.lower() in self.image_extensions]

                if image_files:
                    # Calculate total size
                    total_size = 0
                    for img_file in image_files:
                        try:
                            file_path = Path(root) / img_file
                            total_size += file_path.stat().st_size
                        except:
                            pass

                    # Add to stats
                    if root not in folder_stats:
                        folder_stats[root] = {'count': 0, 'size': 0}

                    folder_stats[root]['count'] += len(image_files)
                    folder_stats[root]['size'] += total_size

                    # Update progress
                    self.progress.emit(root, len(folder_stats))

        except PermissionError:
            pass  # Skip folders we can't access
        except Exception as e:
            pass  # Skip problematic folders


class ImageIndexWorker(QThread):
    """Background thread for indexing images directly."""
    progress = pyqtSignal(str, int, int)  # (message, current, total)
    finished = pyqtSignal(dict)  # stats
    error = pyqtSignal(str)

    def __init__(self, folders: List[str]):
        super().__init__()
        self.folders = folders
        self._is_cancelled = False
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            from .face_indexer import FaceIndexer
            from .clip_indexer import CLIPIndexer

            stats = {'faces': 0, 'images': 0, 'errors': 0}

            # Collect all image files
            all_images = []
            for folder in self.folders:
                for ext in self.image_extensions:
                    all_images.extend(Path(folder).glob(f'*{ext}'))
                    all_images.extend(Path(folder).glob(f'*{ext.upper()}'))

            total = len(all_images)
            self.progress.emit("Initializing face recognition...", 0, total)

            face_indexer = FaceIndexer()
            self.progress.emit("Loading CLIP model...", 0, total)
            clip_indexer = CLIPIndexer()

            for i, image_path in enumerate(all_images):
                if self._is_cancelled:
                    break

                try:
                    self.progress.emit(f"Processing {image_path.name}...", i + 1, total)

                    # Face indexing
                    face_count = face_indexer.index_image(str(image_path))
                    stats['faces'] += face_count

                    # CLIP indexing
                    clip_indexer.index_image(str(image_path))
                    stats['images'] += 1

                except Exception as e:
                    stats['errors'] += 1

            self.finished.emit(stats)

        except Exception as e:
            self.error.emit(str(e))


class ImageFolderScanner(QDialog):
    """Dialog for scanning system for folders containing images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_worker = None
        self.index_worker = None
        self.folder_data = {}  # {folder_path: {'count': int, 'size': int}}
        self.max_size = 0  # For bar graph scaling
        self.checked_items = set()  # Track checked folders
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Find Photo Folders")
        self.setModal(True)
        self.resize(1100, 700)

        # Solarized Light styling
        self.setStyleSheet("""
            QDialog {
                background: #FDF6E3;
            }
            QLabel {
                color: #073642;
                font-size: 10pt;
            }
            QPushButton {
                background: #EEE8D5;
                color: #073642;
                border: 2px solid #D3CBB7;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #E4DFCC;
                border-color: #93A1A1;
            }
            QPushButton:pressed {
                background: #D3CBB7;
            }
            QPushButton:disabled {
                background: #EEE8D5;
                color: #93A1A1;
                border-color: #EEE8D5;
            }
            QTreeWidget {
                background: white;
                color: #073642;
                border: 2px solid #D3CBB7;
                border-radius: 6px;
                font-size: 10pt;
            }
            QTreeWidget::item {
                padding: 6px;
                border-bottom: 1px solid #EEE8D5;
            }
            QTreeWidget::item:hover {
                background: #EEE8D5;
            }
            QTreeWidget::item:selected {
                background: #268BD2;
                color: white;
            }
            QHeaderView::section {
                background: #073642;
                color: #FDF6E3;
                padding: 8px;
                border: none;
                font-weight: bold;
                font-size: 10pt;
            }
            QProgressBar {
                border: 2px solid #D3CBB7;
                border-radius: 4px;
                text-align: center;
                background: white;
                color: #073642;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: #268BD2;
            }
            QCheckBox {
                color: #073642;
                font-size: 10pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #D3CBB7;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #859900;
                border: 2px solid #859900;
            }
            QComboBox {
                background: white;
                color: #073642;
                border: 2px solid #D3CBB7;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10pt;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("🔍 Find Photo Folders")
        header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #073642;")
        main_layout.addWidget(header)

        desc = QLabel(
            "Scan your computer to find all folders containing images. "
            "Check folders to index for face recognition and scene search."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #586E75; font-size: 10pt; font-weight: normal;")
        main_layout.addWidget(desc)

        # Drive selection row
        drive_layout = QHBoxLayout()
        drive_label = QLabel("Scan drives:")
        drive_label.setStyleSheet("font-weight: bold;")
        drive_layout.addWidget(drive_label)

        # Detect available drives
        self.drive_checkboxes = {}
        if os.name == 'nt':  # Windows
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    checkbox = QCheckBox(f"{letter}:")
                    checkbox.setChecked(letter in ['C', 'G'])  # Default C: and G: (Google Drive)
                    checkbox.setStyleSheet("font-weight: normal;")
                    drive_layout.addWidget(checkbox)
                    self.drive_checkboxes[drive] = checkbox
        else:  # Unix-like
            checkbox = QCheckBox("/")
            checkbox.setChecked(True)
            drive_layout.addWidget(checkbox)
            self.drive_checkboxes["/"] = checkbox

        drive_layout.addStretch()
        main_layout.addLayout(drive_layout)

        # Filter and scan row
        filter_layout = QHBoxLayout()

        # Minimum size filter
        filter_label = QLabel("Show folders larger than:")
        filter_label.setStyleSheet("font-weight: normal;")
        filter_layout.addWidget(filter_label)

        self.size_filter = QComboBox()
        self.size_filter.addItems(["All sizes", "1 MB", "10 MB", "50 MB", "100 MB", "500 MB", "1 GB"])
        self.size_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.size_filter)

        filter_layout.addStretch()

        # Scan button
        self.scan_btn = QPushButton("🔍 Start Scan")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background: #268BD2;
                color: white;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: #3498E0;
            }
        """)
        self.scan_btn.clicked.connect(self._start_scan)
        filter_layout.addWidget(self.scan_btn)

        main_layout.addLayout(filter_layout)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet("color: #586E75; font-size: 9pt; font-weight: normal;")
        self.progress_label.setWordWrap(True)
        main_layout.addWidget(self.progress_label)

        # Results tree with checkbox column
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["✓", "Folder Path", "Images", "Size", ""])
        self.results_tree.setColumnWidth(0, 40)   # Checkbox
        self.results_tree.setColumnWidth(1, 450)  # Path
        self.results_tree.setColumnWidth(2, 70)   # Count
        self.results_tree.setColumnWidth(3, 90)   # Size
        self.results_tree.setColumnWidth(4, 300)  # Bar
        self.results_tree.setSortingEnabled(True)
        self.results_tree.setRootIsDecorated(False)
        self.results_tree.itemClicked.connect(self._on_item_clicked)
        main_layout.addWidget(self.results_tree, 1)

        # Selection info
        self.selection_label = QLabel("Check folders to index, then click 'Index Checked Folders'")
        self.selection_label.setStyleSheet("color: #268BD2; font-weight: normal;")
        main_layout.addWidget(self.selection_label)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.check_all_btn = QPushButton("☑ Check All")
        self.check_all_btn.clicked.connect(self._check_all)
        self.check_all_btn.setEnabled(False)
        button_layout.addWidget(self.check_all_btn)

        self.uncheck_all_btn = QPushButton("☐ Uncheck All")
        self.uncheck_all_btn.clicked.connect(self._uncheck_all)
        self.uncheck_all_btn.setEnabled(False)
        button_layout.addWidget(self.uncheck_all_btn)

        button_layout.addStretch()

        self.index_btn = QPushButton("📁 Index Checked Folders")
        self.index_btn.setEnabled(False)
        self.index_btn.setStyleSheet("""
            QPushButton {
                background: #859900;
                color: white;
            }
            QPushButton:hover {
                background: #9FB300;
            }
        """)
        self.index_btn.clicked.connect(self._index_selected)
        button_layout.addWidget(self.index_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

    def _start_scan(self):
        """Start scanning for image folders."""
        # Get selected drives
        selected_drives = [
            drive for drive, checkbox in self.drive_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_drives:
            QMessageBox.warning(self, "No Drives", "Please select at least one drive to scan.")
            return

        # Clear previous results
        self.results_tree.clear()
        self.folder_data.clear()
        self.checked_items.clear()

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Scanning...")
        self.progress_label.setVisible(True)
        self.progress_label.setText("Initializing scan...")

        # Disable buttons
        self.scan_btn.setEnabled(False)
        self.index_btn.setEnabled(False)
        self.check_all_btn.setEnabled(False)
        self.uncheck_all_btn.setEnabled(False)

        # Start scan worker
        self.scan_worker = ImageScanWorker(selected_drives)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()

    def _on_scan_progress(self, current_path: str, total_found: int):
        """Update progress during scan."""
        self.progress_bar.setFormat(f"Found {total_found} folders...")
        # Truncate long paths
        display_path = current_path
        if len(display_path) > 80:
            display_path = "..." + display_path[-77:]
        self.progress_label.setText(f"Scanning: {display_path}")
        QApplication.processEvents()

    def _on_scan_finished(self, folder_data: dict):
        """Handle scan completion."""
        self.folder_data = folder_data
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.scan_btn.setEnabled(True)

        if not folder_data:
            QMessageBox.information(
                self,
                "No Images Found",
                "No folders with images were found on the selected drives."
            )
            return

        # Find max size for bar graph scaling
        self.max_size = max(data['size'] for data in folder_data.values()) if folder_data else 1

        # Populate tree
        self._populate_tree()

        # Enable buttons
        self.index_btn.setEnabled(True)
        self.check_all_btn.setEnabled(True)
        self.uncheck_all_btn.setEnabled(True)

        # Sort by size descending (column 3)
        self.results_tree.sortItems(3, Qt.SortOrder.DescendingOrder)

        self._update_selection_label()

    def _populate_tree(self):
        """Populate tree with folder data, applying current filter."""
        self.results_tree.clear()

        # Get minimum size from filter
        min_size = self._get_min_size()

        for folder_path, data in self.folder_data.items():
            if data['size'] >= min_size:
                self._add_folder_item(folder_path, data)

    def _get_min_size(self) -> int:
        """Get minimum size in bytes from filter dropdown."""
        filter_text = self.size_filter.currentText()
        if filter_text == "All sizes":
            return 0
        elif filter_text == "1 MB":
            return 1 * 1024 * 1024
        elif filter_text == "10 MB":
            return 10 * 1024 * 1024
        elif filter_text == "50 MB":
            return 50 * 1024 * 1024
        elif filter_text == "100 MB":
            return 100 * 1024 * 1024
        elif filter_text == "500 MB":
            return 500 * 1024 * 1024
        elif filter_text == "1 GB":
            return 1024 * 1024 * 1024
        return 0

    def _apply_filter(self):
        """Apply the size filter."""
        if self.folder_data:
            # Remember checked items
            self._populate_tree()
            # Restore check state
            for i in range(self.results_tree.topLevelItemCount()):
                item = self.results_tree.topLevelItem(i)
                folder = item.data(1, Qt.ItemDataRole.UserRole)
                if folder in self.checked_items:
                    item.setText(0, "☑")
            self._update_selection_label()

    def _add_folder_item(self, folder_path: str, data: dict):
        """Add a folder to the results tree."""
        item = QTreeWidgetItem(self.results_tree)

        # Checkbox (column 0)
        checked = folder_path in self.checked_items
        item.setText(0, "☑" if checked else "☐")

        # Folder path (column 1)
        item.setText(1, folder_path)
        item.setData(1, Qt.ItemDataRole.UserRole, folder_path)

        # Image count (column 2)
        item.setText(2, str(data['count']))
        item.setData(2, Qt.ItemDataRole.UserRole, data['count'])

        # Size (column 3)
        size_mb = data['size'] / (1024 * 1024)
        if size_mb < 1:
            size_str = f"{data['size'] / 1024:.1f} KB"
        elif size_mb < 1024:
            size_str = f"{size_mb:.1f} MB"
        else:
            size_gb = size_mb / 1024
            size_str = f"{size_gb:.2f} GB"

        item.setText(3, size_str)
        item.setData(3, Qt.ItemDataRole.UserRole, data['size'])

        # Bar graph (column 4) - just the filled part, different color
        bar_width = 50
        fill_ratio = data['size'] / self.max_size if self.max_size > 0 else 0
        filled = max(1, int(bar_width * fill_ratio))  # At least 1 char

        bar = "█" * filled
        item.setText(4, bar)
        item.setForeground(4, QColor("#268BD2"))

    def _on_item_clicked(self, item, column):
        """Handle item click - toggle checkbox."""
        folder = item.data(1, Qt.ItemDataRole.UserRole)
        if folder in self.checked_items:
            self.checked_items.remove(folder)
            item.setText(0, "☐")
        else:
            self.checked_items.add(folder)
            item.setText(0, "☑")
        self._update_selection_label()

    def _update_selection_label(self):
        """Update the selection count label."""
        count = len(self.checked_items)
        if count == 0:
            self.selection_label.setText("Check folders to index, then click 'Index Checked Folders'")
        else:
            total_images = sum(
                self.folder_data[f]['count'] for f in self.checked_items
                if f in self.folder_data
            )
            total_size = sum(
                self.folder_data[f]['size'] for f in self.checked_items
                if f in self.folder_data
            )
            size_str = f"{total_size / (1024*1024):.1f} MB" if total_size < 1024*1024*1024 else f"{total_size / (1024*1024*1024):.2f} GB"
            self.selection_label.setText(f"✓ {count} folders selected ({total_images} images, {size_str})")

    def _check_all(self):
        """Check all visible folders."""
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            folder = item.data(1, Qt.ItemDataRole.UserRole)
            self.checked_items.add(folder)
            item.setText(0, "☑")
        self._update_selection_label()

    def _uncheck_all(self):
        """Uncheck all folders."""
        self.checked_items.clear()
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            item.setText(0, "☐")
        self._update_selection_label()

    def _on_scan_error(self, error: str):
        """Handle scan error."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.scan_btn.setEnabled(True)

        QMessageBox.critical(
            self,
            "Scan Error",
            f"Error scanning for images:\n{error}"
        )

    def _index_selected(self):
        """Index the checked folders directly."""
        if not self.checked_items:
            QMessageBox.warning(self, "No Selection", "Please check at least one folder to index.")
            return

        selected_folders = list(self.checked_items)
        total_images = sum(self.folder_data[f]['count'] for f in selected_folders if f in self.folder_data)

        result = QMessageBox.question(
            self,
            "Start Indexing",
            f"Index {len(selected_folders)} folders with {total_images} images?\n\n"
            f"This will:\n"
            f"• Detect faces in all images\n"
            f"• Generate scene embeddings (CLIP)\n"
            f"• Enable searches like 'Michelle on the beach'\n\n"
            f"This may take a while for large collections.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total_images)
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)

        # Disable buttons
        self.scan_btn.setEnabled(False)
        self.index_btn.setEnabled(False)
        self.check_all_btn.setEnabled(False)
        self.uncheck_all_btn.setEnabled(False)

        # Start indexing
        self.index_worker = ImageIndexWorker(selected_folders)
        self.index_worker.progress.connect(self._on_index_progress)
        self.index_worker.finished.connect(self._on_index_finished)
        self.index_worker.error.connect(self._on_index_error)
        self.index_worker.start()

    def _on_index_progress(self, message: str, current: int, total: int):
        """Update progress during indexing."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)
        QApplication.processEvents()

    def _on_index_finished(self, stats: dict):
        """Handle indexing completion."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

        # Re-enable buttons
        self.scan_btn.setEnabled(True)
        self.index_btn.setEnabled(True)
        self.check_all_btn.setEnabled(True)
        self.uncheck_all_btn.setEnabled(True)

        QMessageBox.information(
            self,
            "Indexing Complete",
            f"✅ Indexing complete!\n\n"
            f"📸 Images indexed: {stats['images']}\n"
            f"👤 Faces detected: {stats['faces']}\n"
            f"⚠️ Errors: {stats['errors']}\n\n"
            f"You can now:\n"
            f"• Click '👤 Tag Faces' to name detected faces\n"
            f"• Search for images by person or scene"
        )

        # Clear checked items
        self._uncheck_all()

    def _on_index_error(self, error: str):
        """Handle indexing error."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

        # Re-enable buttons
        self.scan_btn.setEnabled(True)
        self.index_btn.setEnabled(True)
        self.check_all_btn.setEnabled(True)
        self.uncheck_all_btn.setEnabled(True)

        QMessageBox.critical(
            self,
            "Indexing Error",
            f"Error indexing images:\n{error}\n\n"
            f"Make sure you have installed:\n"
            f"pip install face_recognition torch torchvision\n"
            f"pip install git+https://github.com/openai/CLIP.git"
        )
