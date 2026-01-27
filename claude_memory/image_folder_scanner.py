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
    QMessageBox, QApplication, QFrame, QHeaderView, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor


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


class ImageFolderScanner(QDialog):
    """Dialog for scanning system for folders containing images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_worker = None
        self.folder_data = {}  # {folder_path: {'count': int, 'size': int}}
        self.max_size = 0  # For bar graph scaling
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
                selection-background-color: #268BD2;
                selection-color: white;
            }
            QTreeWidget::item {
                padding: 8px;
                border-bottom: 1px solid #EEE8D5;
            }
            QTreeWidget::item:hover {
                background: #EEE8D5;
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
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("🔍 Find Photo Folders")
        header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #073642;")
        main_layout.addWidget(header)

        desc = QLabel(
            "Scan your entire computer to find all folders containing images. "
            "Select folders to index for face recognition and scene search."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #586E75; font-size: 10pt; font-weight: normal;")
        main_layout.addWidget(desc)

        # Drive selection
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
                    checkbox.setChecked(True)
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
        main_layout.addWidget(self.scan_btn)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Scanning: %p folders found...")
        main_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet("color: #586E75; font-size: 9pt; font-weight: normal;")
        self.progress_label.setWordWrap(True)
        main_layout.addWidget(self.progress_label)

        # Results tree
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Folder Path", "Images", "Size", "Size (Bar)"])
        self.results_tree.setColumnWidth(0, 500)
        self.results_tree.setColumnWidth(1, 80)
        self.results_tree.setColumnWidth(2, 100)
        self.results_tree.setColumnWidth(3, 300)
        self.results_tree.setSortingEnabled(True)
        self.results_tree.setRootIsDecorated(False)
        self.results_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        main_layout.addWidget(self.results_tree, 1)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.index_btn = QPushButton("📁 Index Selected Folders")
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

        button_layout.addStretch()

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

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)
        self.progress_label.setText("Initializing scan...")

        # Disable buttons
        self.scan_btn.setEnabled(False)
        self.index_btn.setEnabled(False)

        # Start scan worker
        self.scan_worker = ImageScanWorker(selected_drives)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()

    def _on_scan_progress(self, current_path: str, total_found: int):
        """Update progress during scan."""
        self.progress_bar.setValue(total_found)
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
        for folder_path, data in folder_data.items():
            self._add_folder_item(folder_path, data)

        # Enable index button
        self.index_btn.setEnabled(True)

        # Sort by size descending
        self.results_tree.sortItems(2, Qt.SortOrder.DescendingOrder)

        QMessageBox.information(
            self,
            "Scan Complete",
            f"Found {len(folder_data)} folders containing images.\n\n"
            f"Select folders and click 'Index Selected Folders' to enable search."
        )

    def _add_folder_item(self, folder_path: str, data: dict):
        """Add a folder to the results tree."""
        item = QTreeWidgetItem(self.results_tree)

        # Folder path
        item.setText(0, folder_path)
        item.setData(0, Qt.ItemDataRole.UserRole, folder_path)

        # Image count
        item.setText(1, str(data['count']))
        item.setData(1, Qt.ItemDataRole.UserRole, data['count'])  # For sorting

        # Size
        size_mb = data['size'] / (1024 * 1024)
        if size_mb < 1:
            size_str = f"{data['size'] / 1024:.1f} KB"
        elif size_mb < 1024:
            size_str = f"{size_mb:.1f} MB"
        else:
            size_gb = size_mb / 1024
            size_str = f"{size_gb:.2f} GB"

        item.setText(2, size_str)
        item.setData(2, Qt.ItemDataRole.UserRole, data['size'])  # For sorting

        # Bar graph (using unicode blocks)
        bar_width = 40
        fill_ratio = data['size'] / self.max_size if self.max_size > 0 else 0
        filled = int(bar_width * fill_ratio)
        empty = bar_width - filled

        bar = "█" * filled + "░" * empty
        item.setText(3, bar)
        item.setForeground(3, QColor("#268BD2"))

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
        """Index the selected folders."""
        selected_items = self.results_tree.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select at least one folder to index.")
            return

        # Get selected folder paths
        selected_folders = [item.text(0) for item in selected_items]
        total_images = sum(item.data(1, Qt.ItemDataRole.UserRole) for item in selected_items)

        result = QMessageBox.question(
            self,
            "Confirm Indexing",
            f"Index {len(selected_folders)} folders with {total_images} total images?\n\n"
            f"This will enable face recognition and scene search for these images.\n\n"
            f"Note: Indexing may take a while for large collections.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        # Open file discovery dialog for each folder
        from .discovery_dialog import DiscoveryDialog

        QMessageBox.information(
            self,
            "Ready to Index",
            f"The File Discovery dialog will open for each selected folder.\n\n"
            f"Make sure to:\n"
            f"1. Check 'Index images for face & scene search'\n"
            f"2. Select image file types (.jpg, .png, etc.)\n"
            f"3. Click 'Index Selected Files'\n\n"
            f"You'll do this {len(selected_folders)} times."
        )

        self.accept()

        # Launch discovery dialog for first folder
        if selected_folders:
            dialog = DiscoveryDialog(self.parent())
            # TODO: Auto-populate folder path in discovery dialog
            dialog.exec()
