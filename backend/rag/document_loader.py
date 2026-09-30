"""
Extract raw text from uploaded PDF / DOCX / TXT files.
"""
from pathlib import Path


class DocumentExtractionError(Exception):
    pass


def extract_text(file_path: Path, file_type: str) -> str:
    """
    file_type is one of "pdf", "docx", "txt" (without the leading dot).
    Returns cleaned raw text. Raises DocumentExtractionError on failure.
    """
    try:
        if file_type == "pdf":
            return _extract_pdf(file_path)
        elif file_type == "docx":
            return _extract_docx(file_path)
        elif file_type == "txt":
            return _extract_txt(file_path)
        else:
            raise DocumentExtractionError(f"Unsupported file type: {file_type}")
    except DocumentExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DocumentExtractionError(f"Failed to extract text from {file_path.name}: {exc}") from exc


def _extract_pdf(file_path: Path) -> str:
    import fitz  # PyMuPDF

    text_parts = []
    with fitz.open(file_path) as doc:
        if doc.page_count == 0:
            raise DocumentExtractionError("PDF has no pages.")
        for page in doc:
            text_parts.append(page.get_text())
    text = "\n".join(text_parts).strip()
    if not text:
        raise DocumentExtractionError("No extractable text found (the PDF may be scanned/image-only).")
    return text


def _extract_docx(file_path: Path) -> str:
    import docx  # python-docx

    document = docx.Document(str(file_path))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    text = "\n".join(parts).strip()
    if not text:
        raise DocumentExtractionError("No extractable text found in DOCX.")
    return text


def _extract_txt(file_path: Path) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            text = file_path.read_text(encoding=encoding).strip()
            if not text:
                raise DocumentExtractionError("TXT file is empty.")
            return text
        except UnicodeDecodeError:
            continue
    raise DocumentExtractionError("Could not decode TXT file.")


def clean_text(text: str) -> str:
    """Basic whitespace normalization."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)
