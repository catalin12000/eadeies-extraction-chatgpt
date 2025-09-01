from __future__ import annotations

from pathlib import Path


def get_text(pdf_path: Path) -> str:
    """Extract plain text from a PDF using docling.

    Returns empty string if docling is not available.
    """
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception:
        return ""
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    text = result.document.export_to_text() if hasattr(result.document, "export_to_text") else str(result.document)
    return (text or "").strip()
