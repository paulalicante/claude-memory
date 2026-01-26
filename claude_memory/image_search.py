"""
Image search module for Claude Memory.
Combines face recognition and CLIP semantic search.
"""

import torch
import numpy as np
import re
from typing import Optional

from .database import get_connection


class ImageSearch:
    """Search for images using face recognition and/or CLIP semantic search."""

    def __init__(self):
        """Initialize CLIP model for text encoding."""
        import clip

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)

    def search(self, query: str, top_k: int = 20, tolerance: float = 0.6) -> list:
        """
        Search for images matching query.

        Handles:
        - Person names: "Michelle" → face search
        - Scene descriptions: "beach" → CLIP search
        - Combined: "Michelle on the beach" → both face and CLIP search

        Args:
            query: Search query (person name and/or scene description)
            top_k: Maximum number of results to return
            tolerance: Face matching tolerance (lower = stricter, default 0.6)

        Returns:
            List of tuples: (image_path, score, match_info)
            match_info is dict with keys: 'type' ('face', 'scene', 'both'), 'person', 'scores'
        """
        import clip

        conn = get_connection()
        cursor = conn.cursor()

        # Get all known persons
        cursor.execute('SELECT id, name, reference_embedding FROM persons')
        persons = {row[1].lower(): (row[0], row[2]) for row in cursor.fetchall()}

        # Check if query contains a known person name
        person_match = None
        person_name = None
        scene_query = query.strip()

        for name in persons:
            if name in query.lower():
                person_match = persons[name]
                person_name = name
                # Remove name from query for scene search
                scene_query = re.sub(r'\b' + re.escape(name) + r'\b', '', query, flags=re.IGNORECASE).strip()
                scene_query = re.sub(r'\s+', ' ', scene_query)  # clean up spaces
                break

        results = {}  # image_path -> scores dict

        # FACE SEARCH: Find images with matching person
        if person_match:
            person_id, ref_bytes = person_match
            reference = np.frombuffer(ref_bytes, dtype=np.float32)

            cursor.execute('SELECT image_path, embedding FROM face_embeddings')
            for image_path, emb_bytes in cursor.fetchall():
                embedding = np.frombuffer(emb_bytes, dtype=np.float32)
                distance = np.linalg.norm(reference - embedding)

                if distance <= tolerance:
                    face_score = 1.0 - (distance / tolerance)  # Convert to similarity (0-1)
                    if image_path not in results:
                        results[image_path] = {}
                    results[image_path]['face'] = face_score
                    results[image_path]['person'] = person_name

        # CLIP SEARCH: Find images matching scene description
        # Filter out stop words to get meaningful scene description
        stop_words = {'on', 'the', 'a', 'an', 'in', 'at', 'with', 'of', 'by', 'to', 'from'}
        scene_words = [w for w in scene_query.split() if w.lower() not in stop_words and len(w) > 2]

        if scene_words:
            # Use cleaned query for better CLIP matching
            clean_scene_query = ' '.join(scene_words) if scene_words else scene_query

            text = clip.tokenize([clean_scene_query]).to(self.device)
            with torch.no_grad():
                text_embedding = self.model.encode_text(text)
                text_embedding = text_embedding.cpu().numpy().flatten()

            cursor.execute('SELECT image_path, embedding FROM clip_embeddings')
            for image_path, emb_bytes in cursor.fetchall():
                embedding = np.frombuffer(emb_bytes, dtype=np.float32)

                # Cosine similarity
                similarity = np.dot(text_embedding, embedding) / (
                    np.linalg.norm(text_embedding) * np.linalg.norm(embedding)
                )

                if image_path in results:
                    # Already has face match, add scene score
                    results[image_path]['clip'] = float(similarity)
                elif not person_match:
                    # No person filter, include all scene matches
                    results[image_path] = {'clip': float(similarity)}

        conn.close()

        # Combine scores and create final results
        final_results = []

        for path, scores in results.items():
            has_face = 'face' in scores
            has_clip = 'clip' in scores

            # Determine match type and combined score
            if person_match and scene_words:
                # Query has both person and scene
                if has_face and has_clip:
                    # Both must match
                    match_type = 'both'
                    combined_score = scores['face'] * 0.5 + scores['clip'] * 0.5
                    match_info = {
                        'type': match_type,
                        'person': scores.get('person'),
                        'scores': scores
                    }
                    final_results.append((path, combined_score, match_info))
            elif person_match:
                # Person only query
                if has_face:
                    match_type = 'face'
                    combined_score = scores['face']
                    match_info = {
                        'type': match_type,
                        'person': scores.get('person'),
                        'scores': scores
                    }
                    final_results.append((path, combined_score, match_info))
            else:
                # Scene only query
                if has_clip:
                    match_type = 'scene'
                    combined_score = scores['clip']
                    match_info = {
                        'type': match_type,
                        'person': None,
                        'scores': scores
                    }
                    final_results.append((path, combined_score, match_info))

        # Sort by score descending
        final_results.sort(key=lambda x: x[1], reverse=True)

        return final_results[:top_k]

    def get_search_stats(self) -> dict:
        """Get statistics about indexed images and faces."""
        conn = get_connection()
        cursor = conn.cursor()

        stats = {}

        # Total CLIP embeddings
        cursor.execute('SELECT COUNT(*) FROM clip_embeddings')
        stats['total_images'] = cursor.fetchone()[0]

        # Total face embeddings
        cursor.execute('SELECT COUNT(*) FROM face_embeddings')
        stats['total_faces'] = cursor.fetchone()[0]

        # Tagged faces
        cursor.execute('SELECT COUNT(*) FROM face_embeddings WHERE person_id IS NOT NULL')
        stats['tagged_faces'] = cursor.fetchone()[0]

        # Untagged faces
        stats['untagged_faces'] = stats['total_faces'] - stats['tagged_faces']

        # Total persons
        cursor.execute('SELECT COUNT(*) FROM persons')
        stats['total_persons'] = cursor.fetchone()[0]

        conn.close()
        return stats
