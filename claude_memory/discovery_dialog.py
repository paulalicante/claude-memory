"""
File Discovery Dialog for Claude Memory (PyQt6 version).
Scans drives to find documents and lets user select folders to index.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QProgressBar,
    QCheckBox, QFrame, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from .file_indexer import scan_directory, add_watched_folder, index_files, get_file_type_icon


class ScanWorker(QThread):
    """Background thread for scanning directories."""
    progress = pyqtSignal(str, int)  # (current_path, file_count)
    finished = pyqtSignal(dict)  # scan_results
    error = pyqtSignal(str)

    def __init__(self, directory: Path):
        super().__init__()
        self.directory = directory
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            def progress_callback(count):
                if self._is_cancelled:
                    raise InterruptedError("Scan cancelled")
                self.progress.emit(str(self.directory), count)

            results = scan_directory(self.directory, progress_callback)
            self.finished.emit(results)
        except InterruptedError:
            pass
        except Exception as e:
            self.error.emit(str(e))


class DiscoveryDialog(QDialog):
    """Dialog for discovering and selecting folders to index."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_results = {}  # {folder_path: scan_results}
        self.scan_workers = []
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Document Discovery")
        self.setModal(True)
        self.resize(800, 600)

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
                background: #268BD2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #2AA198;
            }
            QPushButton:disabled {
                background: #93A1A1;
            }
            QTreeWidget {
                background: white;
                color: #073642;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                font-size: 10pt;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background: #268BD2;
                color: white;
            }
            QProgressBar {
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                text-align: center;
                background: white;
            }
            QProgressBar::chunk {
                background: #859900;
                border-radius: 5px;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Header
        header = QLabel("Discover Documents on Your Computer")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #073642;")
        main_layout.addWidget(header)

        desc = QLabel(
            "Select which drives or folders to scan for documents. "
            "We'll find all text files, PDFs, Word docs, Excel sheets, and more."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #586E75; font-size: 9pt;")
        main_layout.addWidget(desc)

        # Drive selection
        drive_layout = QHBoxLayout()
        drive_label = QLabel("Scan:")
        drive_label.setStyleSheet("color: #073642; font-weight: bold;")
        drive_layout.addWidget(drive_label)

        self.drive_combo = QComboBox()
        self.drive_combo.setStyleSheet("""
            QComboBox {
                background: white;
                color: #073642;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
            }
        """)
        self._populate_drives()
        drive_layout.addWidget(self.drive_combo, 1)

        self.scan_btn = QPushButton("🔍 Scan Drive")
        self.scan_btn.clicked.connect(self._start_scan)
        drive_layout.addWidget(self.scan_btn)

        main_layout.addLayout(drive_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)  # Indeterminate
        main_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #657B83; font-size: 9pt;")
        self.progress_label.setVisible(False)
        main_layout.addWidget(self.progress_label)

        # Results tree
        results_label = QLabel("Discovered Folders:")
        results_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        main_layout.addWidget(results_label)

        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["📁 Folder", "Files", "Monitor"])
        self.results_tree.setColumnWidth(0, 400)
        self.results_tree.setColumnWidth(1, 100)
        main_layout.addWidget(self.results_tree)

        # Info label
        info_label = QLabel(
            "✓ Check folders to index them | 👁 Enable monitoring to auto-update when files change"
        )
        info_label.setStyleSheet("color: #586E75; font-size: 9pt; font-style: italic;")
        main_layout.addWidget(info_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: #D3CBB7; margin: 5px 0;")
        main_layout.addWidget(separator)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #93A1A1;
                color: white;
            }
            QPushButton:hover {
                background: #657B83;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.index_btn = QPushButton("Index Selected Folders")
        self.index_btn.setEnabled(False)
        self.index_btn.clicked.connect(self._index_selected)
        button_layout.addWidget(self.index_btn)

        main_layout.addLayout(button_layout)

    def _populate_drives(self):
        """Populate the drive combo box with available drives."""
        import string
        from pathlib import Path

        # Add common user folders first
        user_home = Path.home()
        self.drive_combo.addItem(f"🏠 {user_home}", str(user_home))
        self.drive_combo.addItem(f"📄 {user_home / 'Documents'}", str(user_home / 'Documents'))
        self.drive_combo.addItem(f"⬇️ {user_home / 'Downloads'}", str(user_home / 'Downloads'))
        self.drive_combo.addItem(f"🖥️ {user_home / 'Desktop'}", str(user_home / 'Desktop'))

        # Add all available drives
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:/")
            if drive.exists():
                self.drive_combo.addItem(f"💾 {drive}", str(drive))

    def _start_scan(self):
        """Start scanning the selected drive/folder."""
        selected_path = self.drive_combo.currentData()
        if not selected_path:
            return

        path = Path(selected_path)
        if not path.exists():
            QMessageBox.warning(self, "Invalid Path", f"The path {path} does not exist.")
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_label.setText(f"Scanning {path}...")
        self.scan_btn.setEnabled(False)
        self.drive_combo.setEnabled(False)

        # Start scan in background
        worker = ScanWorker(path)
        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(self._on_scan_finished)
        worker.error.connect(self._on_scan_error)
        self.scan_workers.append(worker)
        worker.start()

    def _on_scan_progress(self, path: str, count: int):
        """Update progress during scan."""
        self.progress_label.setText(f"Scanning {path}... {count} files found")

    def _on_scan_finished(self, results: Dict):
        """Handle scan completion."""
        # Hide progress
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.drive_combo.setEnabled(True)

        # Store results
        scanned_path = self.drive_combo.currentData()
        self.scan_results[scanned_path] = results

        # Add to tree
        self._add_result_to_tree(scanned_path, results)

        # Enable index button
        self.index_btn.setEnabled(True)

    def _on_scan_error(self, error: str):
        """Handle scan error."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.drive_combo.setEnabled(True)

        QMessageBox.critical(self, "Scan Error", f"Error scanning directory:\n{error}")

    def _add_result_to_tree(self, folder_path: str, results: Dict):
        """Add scan results to the tree widget."""
        # Create folder item
        item = QTreeWidgetItem(self.results_tree)
        item.setText(0, folder_path)
        item.setText(1, f"{results['total_files']} files")
        item.setData(0, Qt.ItemDataRole.UserRole, folder_path)
        item.setCheckState(0, Qt.CheckState.Checked)

        # Add monitor checkbox
        monitor_checkbox = QCheckBox()
        self.results_tree.setItemWidget(item, 2, monitor_checkbox)

        # Add file type breakdown as children
        for file_type, count in sorted(results['by_type'].items()):
            child = QTreeWidgetItem(item)
            icon = get_file_type_icon(file_type)
            child.setText(0, f"{icon} {file_type} files")
            child.setText(1, str(count))
            child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

        item.setExpanded(True)

    def _index_selected(self):
        """Index the selected folders."""
        selected_folders = []

        # Get checked folders
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                folder_path = item.data(0, Qt.ItemDataRole.UserRole)
                monitor_checkbox = self.results_tree.itemWidget(item, 2)
                is_monitored = monitor_checkbox.isChecked() if monitor_checkbox else False

                selected_folders.append({
                    'path': folder_path,
                    'is_monitored': is_monitored,
                    'results': self.scan_results.get(folder_path)
                })

        if not selected_folders:
            QMessageBox.warning(self, "No Selection", "Please select at least one folder to index.")
            return

        # Index folders
        total_indexed = 0
        for folder_info in selected_folders:
            try:
                # Add to watched folders
                folder_id = add_watched_folder(folder_info['path'], folder_info['is_monitored'])

                # Index files
                if folder_info['results']:
                    count = index_files(folder_id, folder_info['results']['files'])
                    total_indexed += count

            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Indexing Error",
                    f"Error indexing {folder_info['path']}:\n{str(e)}"
                )

        # Show success message
        QMessageBox.information(
            self,
            "Indexing Complete",
            f"Successfully indexed {total_indexed} files from {len(selected_folders)} folders.\n\n"
            f"You can now search these files from the main search window."
        )

        self.accept()
