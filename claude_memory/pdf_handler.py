"""
PDF handling for Claude Memory app.
Import, store, extract text, and render PDFs.
"""

import shutil
from pathlib import Path
from typing import Optional, List, Tuple
import uuid

from .config import get_app_dir

# Try to import PyMuPDF
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    fitz = None

# Try to import PIL for image handling
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None
    ImageTk = None


def get_pdf_storage_dir() -> Path:
    """Get the directory for storing PDF files."""
    pdf_dir = get_app_dir() / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    return pdf_dir


def is_pdf_support_available() -> bool:
    """Check if PDF support is available."""
    return HAS_PYMUPDF and HAS_PIL


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract all text content from a PDF file.
    Returns the extracted text for indexing/searching.
    """
    if not HAS_PYMUPDF:
        return "[PDF text extraction unavailable - install PyMuPDF]"

    try:
        doc = fitz.open(str(pdf_path))
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_parts.append(f"[Page {page_num + 1}]\n{text}")

        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        return f"[Error extracting PDF text: {e}]"


def get_pdf_info(pdf_path: Path) -> dict:
    """Get information about a PDF file."""
    if not HAS_PYMUPDF:
        return {"page_count": 0, "title": "", "author": ""}

    try:
        doc = fitz.open(str(pdf_path))
        info = {
            "page_count": len(doc),
            "title": doc.metadata.get("title", "") or "",
            "author": doc.metadata.get("author", "") or "",
        }
        doc.close()
        return info
    except Exception:
        return {"page_count": 0, "title": "", "author": ""}


def import_pdf(source_path: str) -> Tuple[Optional[str], str, str]:
    """
    Import a PDF file into the storage directory.

    Args:
        source_path: Path to the PDF file to import

    Returns:
        Tuple of (stored_path, extracted_text, title)
        stored_path is None if import failed
    """
    source = Path(source_path)

    if not source.exists():
        return None, "", f"File not found: {source_path}"

    if not source.suffix.lower() == ".pdf":
        return None, "", "File is not a PDF"

    # Generate a unique filename to avoid collisions
    unique_id = uuid.uuid4().hex[:8]
    dest_filename = f"{source.stem}_{unique_id}.pdf"
    dest_path = get_pdf_storage_dir() / dest_filename

    try:
        # Copy the file to storage
        shutil.copy2(source, dest_path)

        # Extract text for searching
        text = extract_text_from_pdf(dest_path)

        # Get title from PDF metadata or filename
        info = get_pdf_info(dest_path)
        title = info.get("title") or source.stem

        return str(dest_path), text, title

    except Exception as e:
        return None, "", f"Error importing PDF: {e}"


def render_pdf_page(pdf_path: str, page_num: int = 0, zoom: float = 1.5) -> Optional["Image.Image"]:
    """
    Render a single page of a PDF as a PIL Image.

    Args:
        pdf_path: Path to the PDF file
        page_num: Page number (0-indexed)
        zoom: Zoom factor (1.5 = 150%)

    Returns:
        PIL Image object or None if rendering failed
    """
    if not HAS_PYMUPDF or not HAS_PIL:
        return None

    try:
        doc = fitz.open(pdf_path)

        if page_num >= len(doc):
            doc.close()
            return None

        page = doc[page_num]

        # Create a transformation matrix for the zoom
        mat = fitz.Matrix(zoom, zoom)

        # Render the page as a pixmap
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        doc.close()
        return img

    except Exception as e:
        print(f"Error rendering PDF page: {e}")
        return None


def get_pdf_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF."""
    if not HAS_PYMUPDF:
        return 0

    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def render_all_pages(pdf_path: str, zoom: float = 1.2) -> List["Image.Image"]:
    """
    Render all pages of a PDF as PIL Images.

    Args:
        pdf_path: Path to the PDF file
        zoom: Zoom factor

    Returns:
        List of PIL Image objects
    """
    if not HAS_PYMUPDF or not HAS_PIL:
        return []

    images = []
    try:
        doc = fitz.open(pdf_path)
        mat = fitz.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

        doc.close()
    except Exception as e:
        print(f"Error rendering PDF pages: {e}")

    return images
