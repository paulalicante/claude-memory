"""
CLIP indexing module for Claude Memory.
Generates semantic embeddings for images using OpenAI's CLIP model.
"""

import torch
import numpy as np
from pathlib import Path
from typing import Optional, Callable
from PIL import Image

from .database import get_connection


class CLIPIndexer:
    """Indexes images using CLIP for semantic/scene search."""

    def __init__(self):
        """Initialize CLIP model."""
        import clip

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)

    def index_image(self, image_path: str, progress_callback: Optional[Callable] = None):
        """
        Generate and store CLIP embedding for an image.

        Args:
            image_path: Path to image file
            progress_callback: Optional callback(message: str)
        """
        try:
            image = self.preprocess(Image.open(image_path)).unsqueeze(0).to(self.device)

            with torch.no_grad():
                embedding = self.model.encode_image(image)
                embedding = embedding.cpu().numpy().flatten()

            embedding_bytes = embedding.astype(np.float32).tobytes()

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO clip_embeddings (image_path, embedding)
                VALUES (?, ?)
            ''', (image_path, embedding_bytes))

            conn.commit()
            conn.close()

            if progress_callback:
                progress_callback(f"Indexed {Path(image_path).name}")

        except Exception as e:
            raise Exception(f"Error indexing {image_path}: {str(e)}")

    def index_directory(
        self,
        directory: str,
        extensions: tuple = ('.jpg', '.jpeg', '.png', '.bmp', '.gif'),
        progress_callback: Optional[Callable] = None
    ) -> dict:
        """
        Index all images in a directory.

        Args:
            directory: Path to directory to scan
            extensions: Image file extensions to process
            progress_callback: Optional callback(message: str)

        Returns:
            Dictionary with stats: {'total_images': int, 'errors': int}
        """
        path = Path(directory)
        stats = {'total_images': 0, 'errors': 0}

        image_files = []
        for ext in extensions:
            image_files.extend(path.rglob(f'*{ext}'))
            image_files.extend(path.rglob(f'*{ext.upper()}'))

        for image_path in image_files:
            try:
                if progress_callback:
                    progress_callback(f"Processing {image_path.name}...")

                self.index_image(str(image_path), progress_callback)
                stats['total_images'] += 1

            except Exception as e:
                stats['errors'] += 1
                if progress_callback:
                    progress_callback(f"Error: {image_path.name}: {str(e)}")

        return stats

    def batch_index_images(self, image_paths: list, progress_callback: Optional[Callable] = None):
        """
        Index multiple images efficiently.

        Args:
            image_paths: List of image paths to index
            progress_callback: Optional callback(message: str)
        """
        for i, image_path in enumerate(image_paths):
            try:
                self.index_image(image_path, progress_callback)

                if progress_callback and (i + 1) % 10 == 0:
                    progress_callback(f"Indexed {i + 1}/{len(image_paths)} images")

            except Exception as e:
                if progress_callback:
                    progress_callback(f"Error: {Path(image_path).name}: {str(e)}")

    def is_indexed(self, image_path: str) -> bool:
        """Check if an image has been indexed."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM clip_embeddings WHERE image_path = ?', (image_path,))
        result = cursor.fetchone()

        conn.close()
        return result is not None

    def get_indexed_count(self) -> int:
        """Get total number of indexed images."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM clip_embeddings')
        count = cursor.fetchone()[0]

        conn.close()
        return count

    def remove_missing_images(self, progress_callback: Optional[Callable] = None) -> int:
        """
        Remove embeddings for images that no longer exist on disk.

        Returns:
            Number of entries removed
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT image_path FROM clip_embeddings')
        all_paths = [row[0] for row in cursor.fetchall()]

        removed = 0
        for image_path in all_paths:
            if not Path(image_path).exists():
                cursor.execute('DELETE FROM clip_embeddings WHERE image_path = ?', (image_path,))
                removed += 1

                if progress_callback:
                    progress_callback(f"Removed missing image: {Path(image_path).name}")

        conn.commit()
        conn.close()

        return removed
