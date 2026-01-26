"""
Face tagging module for Claude Memory.
Tag detected faces with person names and auto-tag similar faces.
"""

import numpy as np
from typing import Optional, Callable

from .database import get_connection


class FaceTagger:
    """Tags faces with person names and manages person database."""

    def __init__(self):
        pass

    def tag_face(self, face_id: int, person_name: str) -> int:
        """
        Tag a specific face with a person's name.

        Args:
            face_id: ID of the face embedding to tag
            person_name: Name of the person

        Returns:
            person_id
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Get or create person
        cursor.execute('SELECT id FROM persons WHERE name = ?', (person_name,))
        row = cursor.fetchone()

        if row:
            person_id = row[0]
        else:
            # Get the embedding from this face to use as reference
            cursor.execute('SELECT embedding FROM face_embeddings WHERE id = ?', (face_id,))
            embedding_row = cursor.fetchone()

            if not embedding_row:
                raise ValueError(f"Face ID {face_id} not found")

            embedding = embedding_row[0]

            cursor.execute('''
                INSERT INTO persons (name, reference_embedding) VALUES (?, ?)
            ''', (person_name, embedding))
            person_id = cursor.lastrowid

        # Update the face record
        cursor.execute('UPDATE face_embeddings SET person_id = ? WHERE id = ?',
                      (person_id, face_id))

        conn.commit()
        conn.close()

        return person_id

    def untag_face(self, face_id: int):
        """Remove person tag from a face."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE face_embeddings SET person_id = NULL WHERE id = ?', (face_id,))

        conn.commit()
        conn.close()

    def auto_tag_similar_faces(
        self,
        person_name: str,
        tolerance: float = 0.6,
        progress_callback: Optional[Callable] = None
    ) -> int:
        """
        Find and tag all faces matching a known person.

        Args:
            person_name: Name of person to match
            tolerance: Similarity threshold (lower = more strict, 0.6 is default)
            progress_callback: Optional callback(message: str)

        Returns:
            Number of faces tagged
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Get reference embedding
        cursor.execute('''
            SELECT id, reference_embedding FROM persons WHERE name = ?
        ''', (person_name,))
        row = cursor.fetchone()

        if not row:
            return 0

        person_id, ref_bytes = row
        reference = np.frombuffer(ref_bytes, dtype=np.float32)

        # Get all untagged faces
        cursor.execute('SELECT id, embedding FROM face_embeddings WHERE person_id IS NULL')
        untagged = cursor.fetchall()

        if progress_callback:
            progress_callback(f"Comparing {len(untagged)} untagged faces...")

        tagged_count = 0
        for face_id, emb_bytes in untagged:
            embedding = np.frombuffer(emb_bytes, dtype=np.float32)

            # Compare faces (Euclidean distance)
            distance = np.linalg.norm(reference - embedding)

            if distance <= tolerance:
                cursor.execute('UPDATE face_embeddings SET person_id = ? WHERE id = ?',
                             (person_id, face_id))
                tagged_count += 1

                if progress_callback and tagged_count % 10 == 0:
                    progress_callback(f"Tagged {tagged_count} matches...")

        conn.commit()
        conn.close()

        if progress_callback:
            progress_callback(f"Auto-tagged {tagged_count} faces for {person_name}")

        return tagged_count

    def get_all_persons(self) -> list:
        """
        Get list of all known persons.

        Returns:
            List of dictionaries with person data
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.id, p.name, p.created_at, COUNT(f.id) as face_count
            FROM persons p
            LEFT JOIN face_embeddings f ON p.id = f.person_id
            GROUP BY p.id
            ORDER BY p.name
        ''')

        persons = []
        for row in cursor.fetchall():
            persons.append({
                'id': row[0],
                'name': row[1],
                'created_at': row[2],
                'face_count': row[3]
            })

        conn.close()
        return persons

    def get_person_by_name(self, name: str) -> Optional[dict]:
        """Get person details by name."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.id, p.name, p.created_at, COUNT(f.id) as face_count
            FROM persons p
            LEFT JOIN face_embeddings f ON p.id = f.person_id
            WHERE p.name = ?
            GROUP BY p.id
        ''', (name,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'created_at': row[2],
                'face_count': row[3]
            }
        return None

    def delete_person(self, person_id: int):
        """
        Delete a person and untag all their faces.

        Args:
            person_id: ID of person to delete
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Untag all faces first
        cursor.execute('UPDATE face_embeddings SET person_id = NULL WHERE person_id = ?',
                      (person_id,))

        # Delete person
        cursor.execute('DELETE FROM persons WHERE id = ?', (person_id,))

        conn.commit()
        conn.close()

    def rename_person(self, person_id: int, new_name: str):
        """
        Rename a person.

        Args:
            person_id: ID of person to rename
            new_name: New name
        """
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('UPDATE persons SET name = ? WHERE id = ?', (new_name, person_id))

        conn.commit()
        conn.close()
