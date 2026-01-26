"""
Face Tagging Dialog for Claude Memory (PyQt6 version).
Shows detected faces and allows user to tag them with person names.
"""

from pathlib import Path
from typing import Optional
from PIL import Image as PILImage
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QLineEdit,
    QMessageBox, QApplication, QFrame, QGridLayout,
    QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont, QImage

from .face_indexer import FaceIndexer
from .face_tagger import FaceTagger


class AutoTagWorker(QThread):
    """Background thread for auto-tagging similar faces."""
    progress = pyqtSignal(str)  # status_message
    finished = pyqtSignal(int)  # tagged_count
    error = pyqtSignal(str)

    def __init__(self, person_name: str, tolerance: float = 0.6):
        super().__init__()
        self.person_name = person_name
        self.tolerance = tolerance
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            tagger = FaceTagger()
            count = tagger.auto_tag_similar_faces(
                self.person_name,
                self.tolerance,
                lambda msg: self.progress.emit(msg) if not self._is_cancelled else None
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class FaceTaggingDialog(QDialog):
    """Dialog for tagging detected faces with person names."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.face_indexer = FaceIndexer()
        self.face_tagger = FaceTagger()
        self.untagged_faces = []
        self.current_page = 0
        self.faces_per_page = 12
        self.face_widgets = []  # List of (frame, face_data)
        self.auto_tag_worker = None
        self._init_ui()
        self._load_untagged_faces()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Tag Faces")
        self.setModal(True)
        self.resize(1000, 700)

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
            QLineEdit, QComboBox {
                background: white;
                color: #073642;
                border: 2px solid #D3CBB7;
                border-radius: 4px;
                padding: 6px;
                font-size: 10pt;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #268BD2;
            }
            QGroupBox {
                color: #073642;
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #D3CBB7;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                background: #EEE8D5;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel("Tag Detected Faces")
        header.setStyleSheet("font-size: 16pt; font-weight: bold; color: #073642;")
        main_layout.addWidget(header)

        desc = QLabel(
            "Tag faces with person names to enable search like \"Michelle on the beach\". "
            "After tagging one face, auto-tag will find all similar faces."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #586E75; font-size: 10pt; font-weight: normal;")
        main_layout.addWidget(desc)

        # Stats
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #268BD2; font-size: 10pt; font-weight: normal;")
        main_layout.addWidget(self.stats_label)

        # Scroll area for faces
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #FDF6E3; }")

        scroll_content = QWidget()
        self.faces_layout = QGridLayout(scroll_content)
        self.faces_layout.setSpacing(15)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)

        # Pagination
        pagination_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.clicked.connect(self._previous_page)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet("font-weight: normal;")
        pagination_layout.addWidget(self.page_label, 1)

        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self._next_page)
        pagination_layout.addWidget(self.next_btn)

        main_layout.addLayout(pagination_layout)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._load_untagged_faces)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Done")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #859900;
                color: white;
            }
            QPushButton:hover {
                background: #9FB300;
            }
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

    def _load_untagged_faces(self):
        """Load untagged faces from database."""
        self.untagged_faces = self.face_indexer.get_untagged_faces(limit=1000)
        self.current_page = 0
        self._update_stats()
        self._display_current_page()

    def _update_stats(self):
        """Update statistics label."""
        total = len(self.untagged_faces)
        if total == 0:
            self.stats_label.setText("✅ No untagged faces! All faces have been tagged.")
        else:
            self.stats_label.setText(f"📊 {total} untagged faces found")

    def _display_current_page(self):
        """Display faces for the current page."""
        # Clear existing widgets
        for widget, _ in self.face_widgets:
            widget.deleteLater()
        self.face_widgets.clear()

        # Calculate page range
        start = self.current_page * self.faces_per_page
        end = min(start + self.faces_per_page, len(self.untagged_faces))
        page_faces = self.untagged_faces[start:end]

        # Display faces in grid (4 columns)
        cols = 4
        for i, face in enumerate(page_faces):
            row = i // cols
            col = i % cols
            face_widget = self._create_face_widget(face)
            self.faces_layout.addWidget(face_widget, row, col)
            self.face_widgets.append((face_widget, face))

        # Update pagination
        total_pages = (len(self.untagged_faces) + self.faces_per_page - 1) // self.faces_per_page
        if total_pages == 0:
            total_pages = 1

        self.page_label.setText(f"Page {self.current_page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(end < len(self.untagged_faces))

    def _create_face_widget(self, face: dict) -> QFrame:
        """Create a widget for a single face."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px solid #D3CBB7;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        frame.setFixedSize(220, 280)

        layout = QVBoxLayout(frame)
        layout.setSpacing(8)

        # Load and display face thumbnail
        try:
            image_path = face['image_path']
            bbox = face['bbox']

            # Load full image
            pil_image = PILImage.open(image_path)

            # Crop to face bounding box with some padding
            padding = 30
            left = max(0, bbox['left'] - padding)
            top = max(0, bbox['top'] - padding)
            right = min(pil_image.width, bbox['right'] + padding)
            bottom = min(pil_image.height, bbox['bottom'] + padding)

            face_crop = pil_image.crop((left, top, right, bottom))

            # Resize to thumbnail
            face_crop.thumbnail((180, 180), PILImage.Resampling.LANCZOS)

            # Convert to QPixmap
            face_crop = face_crop.convert('RGB')
            data = face_crop.tobytes('raw', 'RGB')
            qimage = QImage(data, face_crop.width, face_crop.height, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            thumb_label = QLabel()
            thumb_label.setPixmap(pixmap)
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(thumb_label)

        except Exception as e:
            error_label = QLabel(f"❌ Error loading\n{str(e)[:30]}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: #DC322F; font-size: 8pt; font-weight: normal;")
            layout.addWidget(error_label)

        # File name
        file_label = QLabel(Path(face['image_path']).name)
        file_label.setWordWrap(True)
        file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_label.setStyleSheet("font-size: 8pt; color: #586E75; font-weight: normal;")
        layout.addWidget(file_label)

        # Name input
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter name...")
        name_input.setStyleSheet("font-size: 9pt;")
        layout.addWidget(name_input)

        # Tag button
        tag_btn = QPushButton("Tag")
        tag_btn.setStyleSheet("""
            QPushButton {
                background: #268BD2;
                color: white;
                font-size: 9pt;
                padding: 4px;
            }
            QPushButton:hover {
                background: #3498E0;
            }
        """)
        tag_btn.clicked.connect(lambda: self._tag_face(face['id'], name_input.text(), frame))
        layout.addWidget(tag_btn)

        return frame

    def _tag_face(self, face_id: int, person_name: str, widget: QFrame):
        """Tag a face with a person name."""
        if not person_name.strip():
            QMessageBox.warning(self, "No Name", "Please enter a person's name.")
            return

        try:
            # Tag the face
            self.face_tagger.tag_face(face_id, person_name.strip())

            # Ask if user wants to auto-tag similar faces
            result = QMessageBox.question(
                self,
                "Auto-Tag Similar Faces?",
                f"Face tagged as '{person_name}'!\n\n"
                f"Would you like to automatically tag all similar faces as '{person_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if result == QMessageBox.StandardButton.Yes:
                self._auto_tag_similar(person_name.strip())
            else:
                # Just remove this face from the list
                widget.setVisible(False)
                self._load_untagged_faces()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to tag face:\n{str(e)}")

    def _auto_tag_similar(self, person_name: str):
        """Auto-tag all similar faces."""
        # Create progress dialog
        progress_dialog = QMessageBox(self)
        progress_dialog.setWindowTitle("Auto-Tagging")
        progress_dialog.setText(f"Finding all faces similar to {person_name}...")
        progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)

        progress_label = QLabel("Initializing...")
        progress_label.setStyleSheet("font-family: monospace; font-size: 9pt; font-weight: normal;")

        layout = progress_dialog.layout()
        layout.addWidget(progress_label, layout.rowCount(), 0, 1, layout.columnCount())
        progress_dialog.show()

        # Start auto-tagging in background
        self.auto_tag_worker = AutoTagWorker(person_name)
        self.auto_tag_worker.progress.connect(lambda msg: progress_label.setText(msg))
        self.auto_tag_worker.finished.connect(lambda count: self._on_auto_tag_finished(count, progress_dialog))
        self.auto_tag_worker.error.connect(lambda err: self._on_auto_tag_error(err, progress_dialog))
        self.auto_tag_worker.start()

    def _on_auto_tag_finished(self, count: int, dialog: QMessageBox):
        """Handle auto-tag completion."""
        dialog.close()
        dialog.deleteLater()

        QMessageBox.information(
            self,
            "Auto-Tag Complete",
            f"✅ Tagged {count} additional faces!"
        )

        # Reload untagged faces
        self._load_untagged_faces()

    def _on_auto_tag_error(self, error: str, dialog: QMessageBox):
        """Handle auto-tag error."""
        dialog.close()
        dialog.deleteLater()

        QMessageBox.critical(
            self,
            "Auto-Tag Error",
            f"Error auto-tagging faces:\n{error}"
        )

    def _previous_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._display_current_page()

    def _next_page(self):
        """Go to next page."""
        max_page = (len(self.untagged_faces) + self.faces_per_page - 1) // self.faces_per_page - 1
        if self.current_page < max_page:
            self.current_page += 1
            self._display_current_page()
