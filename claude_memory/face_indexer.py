"""
Face indexing module for Claude Memory.
Detects faces in images and stores 128-dimensional embeddings.
"""

import face_recognition
import numpy as np
from pathlib import Path
from typing import Optional, Callable

from .database import get_connection


class FaceIndexer:
    """Indexes faces in images using face_recognition library."""

    def __init__(self):
        pass

    def index_image(self, image_path: str, progress_callback: Optional[Callable] = None) -> int:
        """
        Index all faces in an image.

        Args:
            image_path: Path to image file
            progress_callback: Optional callback function to report progress

        Returns:
            Count of faces found and indexed
        """
        try:
            image = face_recognition.load_image_file(image_path)

            # Get face locations and encodings
            locations = face_recognition.face_locations(image)
            encodings = face_recognition.face_encodings(image, locations)

            if progress_callback:
                progress_callback(f"Found {len(encodings)} faces in {Path(image_path).name}")

            conn = get_connection()
            cursor = conn.cursor()

            for location, encoding in zip(locations, encodings):
                top, right, bottom, left = location
                embedding_bytes = encoding.astype(np.float32).tobytes()

                cursor.execute('''
                    INSERT INTO face_embeddings
                    (image_path, embedding, bbox_left, bbox_top, bbox_right, bbox_bottom)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (image_path, embedding_bytes, left, top, right, bottom))

            conn.commit()
            conn.close()

            return len(encodings)

        except Exception as e:
            raise Exception(f"Error indexing {image_path}: {str(e)}")

    def index_directory(
        self,
        directory: str,
        extensions: tuple = ('.jpg', '.jpeg', '.png', '.bmp', '.gif'),
        progress_callback: Optional[Callable] = None
    ) -> dict:
        """
        Index all images in a directory recursively.

        Args:
            directory: Path to directory to scan
            extensions: Image file extensions to process
            progress_callback: Optional callback(message: str)

        Returns:
            Dictionary with stats: {'total_images': int, 'total_faces': int, 'errors': int}
        """
        path = Path(directory)
        stats = {'total_images': 0, 'total_faces': 0, 'errors': 0}

        image_files = []
        for ext in extensions:
            image_files.extend(path.rglob(f'*{ext}'))
            image_files.extend(path.rglob(f'*{ext.upper()}'))

        for image_path in image_files:
            try:
                if progress_callback:
                    progress_callback(f"Processing {image_path.name}...")

                count = self.index_image(str(image_path), progress_callback)
                stats['total_images'] += 1
                stats['total_faces'] += count

                if progress_callback:
                    progress_callback(f"Indexed {count} faces in {image_path.name}")

            except Exception as e:
                stats['errors'] += 1
                if progress_callback:
                    progress_callback(f"Error: {image_path.name}: {str(e)}")

        return stats

    def get_all_faces(self, image_path: Optional[str] = None) -> list:
        """
        Get all indexed faces, optionally filtered by image path.

        Args:
            image_path: Optional filter by image path

        Returns:
            List of dictionaries with face data
        """
        conn = get_connection()
        cursor = conn.cursor()

        if image_path:
            cursor.execute('''
                SELECT f.id, f.image_path, f.bbox_left, f.bbox_top,
                       f.bbox_right, f.bbox_bottom, p.name
                FROM face_embeddings f
                LEFT JOIN persons p ON f.person_id = p.id
                WHERE f.image_path = ?
                ORDER BY f.created_at DESC
            ''', (image_path,))
        else:
            cursor.execute('''
                SELECT f.id, f.image_path, f.bbox_left, f.bbox_top,
                       f.bbox_right, f.bbox_bottom, p.name
                FROM face_embeddings f
                LEFT JOIN persons p ON f.person_id = p.id
                ORDER BY f.created_at DESC
            ''')

        faces = []
        for row in cursor.fetchall():
            faces.append({
                'id': row[0],
                'image_path': row[1],
                'bbox': {
                    'left': row[2],
                    'top': row[3],
                    'right': row[4],
                    'bottom': row[5]
                },
                'person_name': row[6]  # None if not tagged
            })

        conn.close()
        return faces

    def get_untagged_faces(self, limit: int = 100) -> list:
        """
        Get faces that haven't been tagged with a person name yet.

        Args:
            limit: Maximum number of faces to return

        Returns:
            List of face dictionaries
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, image_path, bbox_left, bbox_top, bbox_right, bbox_bottom
            FROM face_embeddings
            WHERE person_id IS NULL
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))

        faces = []
        for row in cursor.fetchall():
            faces.append({
                'id': row[0],
                'image_path': row[1],
                'bbox': {
                    'left': row[2],
                    'top': row[3],
                    'right': row[4],
                    'bottom': row[5]
                }
            })

        conn.close()
        return faces
