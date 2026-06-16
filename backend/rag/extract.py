"""
Text extraction from uploaded files (Phase 2).

Supports plain text/markdown directly and PDFs via pypdf. Other types raise a
clear error so the API can return a helpful 400.
"""
import io


def extract_text(filename: str, raw: bytes) -> str:
    """Extract plain text from an uploaded file's bytes."""
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages).strip()

    if name.endswith((".txt", ".md", ".markdown", ".text", "")) or not name:
        # Best-effort decode for text-like files.
        return raw.decode("utf-8", errors="ignore").strip()

    raise ValueError(
        f"Unsupported file type: {filename!r}. Upload .txt, .md, or .pdf."
    )
