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
    QCheckBox, QFrame, QMessageBox, QFileDialog, QGroupBox,
    QScrollArea, QWidget, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from .file_indexer import scan_directory, add_watched_folder, index_files, get_file_type_icon, get_watched_folders, remove_watched_folder


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
        self.scan_results = None  # Current scan results
        self.scanned_folder = None
        self.scan_worker = None
        self.file_type_checkboxes = {}  # {file_type: checkbox}
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Document Discovery & Indexing")
        self.setModal(True)
        self.resize(900, 700)

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
            QGroupBox {
                color: #073642;
                border: 2px solid #D3CBB7;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 11pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
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
                background: #268BD2;
                border-color: #268BD2;
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
        header = QLabel("Document Discovery & Indexing")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #073642;")
        main_layout.addWidget(header)

        desc = QLabel(
            "Select folders to scan and index. You can add multiple folders in one session."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #586E75; font-size: 9pt;")
        main_layout.addWidget(desc)

        # Indexed folders list (at top)
        self.indexed_group = QGroupBox("Currently Indexed Folders")
        self.indexed_group.setVisible(False)
        indexed_layout = QVBoxLayout(self.indexed_group)

        self.indexed_list = QTreeWidget()
        self.indexed_list.setHeaderLabels(["📁 Folder", "Files", "Monitored"])
        self.indexed_list.setColumnWidth(0, 400)
        self.indexed_list.setMaximumHeight(150)
        self.indexed_list.setStyleSheet("""
            QTreeWidget {
                background: white;
                color: #073642;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                font-size: 9pt;
            }
            QTreeWidget::item {
                padding: 3px;
            }
        """)
        indexed_layout.addWidget(self.indexed_list)

        remove_btn_layout = QHBoxLayout()
        remove_btn_layout.addStretch()
        self.remove_folder_btn = QPushButton("Remove Selected")
        self.remove_folder_btn.setStyleSheet("""
            QPushButton {
                background: #DC322F;
                padding: 5px 10px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #CB4B16;
            }
        """)
        self.remove_folder_btn.clicked.connect(self._remove_selected_folder)
        remove_btn_layout.addWidget(self.remove_folder_btn)
        indexed_layout.addLayout(remove_btn_layout)

        main_layout.addWidget(self.indexed_group)

        # Load existing indexed folders
        self._refresh_indexed_folders()

        # Folder selection
        folder_group = QGroupBox("Step 1: Choose Folder to Scan")
        folder_layout = QVBoxLayout(folder_group)

        folder_select_layout = QHBoxLayout()

        folder_label = QLabel("Folder:")
        folder_label.setStyleSheet("color: #073642; font-weight: normal;")
        folder_select_layout.addWidget(folder_label)

        self.folder_path_edit = QLabel("(No folder selected)")
        self.folder_path_edit.setStyleSheet("""
            QLabel {
                background: white;
                color: #657B83;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
            }
        """)
        folder_select_layout.addWidget(self.folder_path_edit, 1)

        self.browse_btn = QPushButton("📁 Browse...")
        self.browse_btn.clicked.connect(self._browse_folder)
        folder_select_layout.addWidget(self.browse_btn)

        folder_layout.addLayout(folder_select_layout)

        # Recursive checkbox
        self.recursive_checkbox = QCheckBox("Scan all subfolders recursively")
        self.recursive_checkbox.setChecked(True)
        self.recursive_checkbox.setStyleSheet("font-weight: normal;")
        folder_layout.addWidget(self.recursive_checkbox)

        # Scan button
        scan_button_layout = QHBoxLayout()
        scan_button_layout.addStretch()

        self.scan_btn = QPushButton("🔍 Start Scan")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self._start_scan)
        scan_button_layout.addWidget(self.scan_btn)

        folder_layout.addLayout(scan_button_layout)

        main_layout.addWidget(folder_group)

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

        # File type selection (initially hidden)
        self.filetype_group = QGroupBox("Step 2: Select File Types to Index")
        self.filetype_group.setVisible(False)
        filetype_layout = QVBoxLayout(self.filetype_group)

        # Scroll area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                background: white;
            }
        """)

        self.filetype_widget = QWidget()
        self.filetype_layout = QVBoxLayout(self.filetype_widget)
        self.filetype_layout.setContentsMargins(10, 10, 10, 10)
        scroll.setWidget(self.filetype_widget)

        filetype_layout.addWidget(scroll)

        # Select/Deselect all buttons
        select_buttons = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet("""
            QPushButton {
                background: #859900;
                padding: 5px 10px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #719E00;
            }
        """)
        select_all_btn.clicked.connect(self._select_all_types)
        select_buttons.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setStyleSheet("""
            QPushButton {
                background: #93A1A1;
                padding: 5px 10px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background: #657B83;
            }
        """)
        deselect_all_btn.clicked.connect(self._deselect_all_types)
        select_buttons.addWidget(deselect_all_btn)

        select_buttons.addStretch()
        filetype_layout.addLayout(select_buttons)

        main_layout.addWidget(self.filetype_group)

        # Monitor option (initially hidden)
        self.monitor_group = QGroupBox("Step 3: Monitoring Options")
        self.monitor_group.setVisible(False)
        monitor_layout = QVBoxLayout(self.monitor_group)

        self.monitor_checkbox = QCheckBox("Enable active monitoring (auto-update when files change)")
        self.monitor_checkbox.setStyleSheet("font-weight: normal;")
        monitor_layout.addWidget(self.monitor_checkbox)

        monitor_note = QLabel(
            "⚠️ Monitoring uses system resources. Only enable for folders that change frequently."
        )
        monitor_note.setWordWrap(True)
        monitor_note.setStyleSheet("color: #CB4B16; font-size: 9pt; font-style: italic; font-weight: normal;")
        monitor_layout.addWidget(monitor_note)

        main_layout.addWidget(self.monitor_group)

        # Spacer
        main_layout.addStretch()

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: #D3CBB7; margin: 5px 0;")
        main_layout.addWidget(separator)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        done_btn = QPushButton("Done")
        done_btn.setStyleSheet("""
            QPushButton {
                background: #859900;
                color: white;
            }
            QPushButton:hover {
                background: #719E00;
            }
        """)
        done_btn.clicked.connect(self.accept)
        button_layout.addWidget(done_btn)

        self.index_btn = QPushButton("Index Selected Files")
        self.index_btn.setEnabled(False)
        self.index_btn.setStyleSheet("""
            QPushButton {
                background: #859900;
            }
            QPushButton:hover {
                background: #719E00;
            }
        """)
        self.index_btn.clicked.connect(self._index_selected)
        button_layout.addWidget(self.index_btn)

        main_layout.addLayout(button_layout)

    def _browse_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Scan",
            str(Path.home()),
            QFileDialog.Option.ShowDirsOnly
        )

        if folder:
            self.folder_path_edit.setText(folder)
            self.folder_path_edit.setStyleSheet("""
                QLabel {
                    background: white;
                    color: #073642;
                    border: 1px solid #D3CBB7;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 10pt;
                }
            """)
            self.scan_btn.setEnabled(True)

    def _start_scan(self):
        """Start scanning the selected folder."""
        folder_path = self.folder_path_edit.text()
        if folder_path == "(No folder selected)":
            return

        path = Path(folder_path)
        if not path.exists():
            QMessageBox.warning(self, "Invalid Path", f"The path {path} does not exist.")
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_label.setText(f"Scanning {path}...")
        self.scan_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)

        # Hide previous results
        self.filetype_group.setVisible(False)
        self.monitor_group.setVisible(False)
        self.index_btn.setEnabled(False)

        # Start scan in background
        self.scan_worker = ScanWorker(path)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()

    def _on_scan_progress(self, path: str, count: int):
        """Update progress during scan."""
        self.progress_label.setText(f"Scanning... {count} files found")

    def _on_scan_finished(self, results: Dict):
        """Handle scan completion."""
        # Hide progress
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)

        # Store results
        self.scan_results = results
        self.scanned_folder = self.folder_path_edit.text()

        # Show file type selection
        self._populate_file_types(results['by_type'])
        self.filetype_group.setVisible(True)
        self.monitor_group.setVisible(True)
        self.index_btn.setEnabled(True)

        # Show summary
        total = results['total_files']
        types = len(results['by_type'])
        QMessageBox.information(
            self,
            "Scan Complete",
            f"Found {total} files of {types} different types.\n\n"
            f"Select which file types you want to index below."
        )

    def _on_scan_error(self, error: str):
        """Handle scan error."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)

        QMessageBox.critical(self, "Scan Error", f"Error scanning directory:\n{error}")

    def _populate_file_types(self, by_type: Dict):
        """Populate file type checkboxes."""
        # Clear existing checkboxes
        while self.filetype_layout.count():
            child = self.filetype_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.file_type_checkboxes.clear()

        # Add checkbox for each file type
        for file_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            checkbox = QCheckBox(f"{get_file_type_icon(file_type)} {file_type} ({count} files)")
            checkbox.setChecked(True)  # All selected by default
            checkbox.setStyleSheet("font-weight: normal;")
            self.filetype_layout.addWidget(checkbox)
            self.file_type_checkboxes[file_type] = checkbox

        self.filetype_layout.addStretch()

    def _select_all_types(self):
        """Select all file type checkboxes."""
        for checkbox in self.file_type_checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all_types(self):
        """Deselect all file type checkboxes."""
        for checkbox in self.file_type_checkboxes.values():
            checkbox.setChecked(False)

    def _index_selected(self):
        """Index the selected file types."""
        if not self.scan_results:
            return

        # Get selected file types
        selected_types = [
            file_type for file_type, checkbox in self.file_type_checkboxes.items()
            if checkbox.isChecked()
        ]

        if not selected_types:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select at least one file type to index."
            )
            return

        # Filter files by selected types
        filtered_files = [
            f for f in self.scan_results['files']
            if f['type'] in selected_types
        ]

        if not filtered_files:
            QMessageBox.warning(
                self,
                "No Files",
                "No files match the selected file types."
            )
            return

        # Show confirmation
        total = len(filtered_files)
        types = len(selected_types)
        result = QMessageBox.question(
            self,
            "Confirm Indexing",
            f"Index {total} files of {types} types from:\n{self.scanned_folder}\n\n"
            f"This will add them to your searchable database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result != QMessageBox.StandardButton.Yes:
            return

        # Index files
        try:
            # Add to watched folders
            folder_id = add_watched_folder(
                self.scanned_folder,
                self.monitor_checkbox.isChecked()
            )

            # Index files with progress
            progress = QProgressBar(self)
            progress.setMaximum(len(filtered_files))
            progress.setFormat("Indexing: %v / %m files")

            # Simple modal progress dialog
            progress_dialog = QMessageBox(self)
            progress_dialog.setWindowTitle("Indexing...")
            progress_dialog.setText("Indexing files, please wait...")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            layout = progress_dialog.layout()
            layout.addWidget(progress, layout.rowCount(), 0, 1, layout.columnCount())
            progress_dialog.show()
            QApplication.processEvents()

            def update_progress(current, total):
                progress.setValue(current)
                QApplication.processEvents()

            count = index_files(folder_id, filtered_files, update_progress)

            progress_dialog.close()

            # Show success message
            QMessageBox.information(
                self,
                "Indexing Complete",
                f"Successfully indexed {count} files from:\n{self.scanned_folder}\n\n"
                f"You can add more folders or click Done to finish."
            )

            # Refresh the indexed folders list
            self._refresh_indexed_folders()

            # Reset UI for next folder
            self._reset_scan_ui()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Indexing Error",
                f"Error indexing files:\n{str(e)}"
            )

    def _refresh_indexed_folders(self):
        """Refresh the list of indexed folders."""
        self.indexed_list.clear()

        folders = get_watched_folders()
        if folders:
            self.indexed_group.setVisible(True)
            for folder in folders:
                item = QTreeWidgetItem(self.indexed_list)
                item.setText(0, folder['path'])
                item.setText(1, str(folder['file_count']))
                item.setText(2, "Yes" if folder['is_monitored'] else "No")
                item.setData(0, Qt.ItemDataRole.UserRole, folder['id'])
        else:
            self.indexed_group.setVisible(False)

    def _remove_selected_folder(self):
        """Remove the selected indexed folder."""
        selected = self.indexed_list.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a folder to remove.")
            return

        item = selected[0]
        folder_path = item.text(0)
        folder_id = item.data(0, Qt.ItemDataRole.UserRole)

        result = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove folder from index?\n{folder_path}\n\n"
            f"This will remove all indexed files from this folder.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result == QMessageBox.StandardButton.Yes:
            try:
                remove_watched_folder(folder_id)
                self._refresh_indexed_folders()
                QMessageBox.information(self, "Removed", "Folder removed from index.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove folder:\n{str(e)}")

    def _reset_scan_ui(self):
        """Reset the UI to allow scanning another folder."""
        self.folder_path_edit.setText("(No folder selected)")
        self.folder_path_edit.setStyleSheet("""
            QLabel {
                background: white;
                color: #657B83;
                border: 1px solid #D3CBB7;
                border-radius: 6px;
                padding: 8px;
                font-size: 10pt;
            }
        """)
        self.scan_btn.setEnabled(False)
        self.recursive_checkbox.setChecked(True)
        self.filetype_group.setVisible(False)
        self.monitor_group.setVisible(False)
        self.index_btn.setEnabled(False)
        self.scan_results = None
        self.scanned_folder = None
