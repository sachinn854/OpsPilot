"""
Text chunking (Phase 2).

Splits a long document into overlapping character windows. Overlap keeps context
from spilling across a hard cut, so a sentence split between two chunks still has
a good chance of being retrievable. We try to break on paragraph/sentence
boundaries near the window edge for cleaner chunks.
"""
from backend.config import settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split `text` into overlapping chunks (defaults from settings)."""
    chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
    overlap = overlap or settings.RAG_CHUNK_OVERLAP

    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)

        # Try to end on a natural boundary near the window edge.
        if end < n:
            window = text[start:end]
            for sep in ("\n\n", "\n", ". ", " "):
                cut = window.rfind(sep)
                # Only honor the boundary if it's reasonably far in.
                if cut != -1 and cut > chunk_size * 0.5:
                    end = start + cut + len(sep)
                    break

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks
