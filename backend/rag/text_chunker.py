"""
Split cleaned text into overlapping chunks suitable for embedding.
"""
from typing import List

from backend.config import settings


def chunk_text(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
) -> List[str]:
    """
    Word-based sliding-window chunking. Keeps chunks roughly `chunk_size`
    characters long with `overlap` characters shared between consecutive chunks.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    if not text:
        return []

    words = text.split()
    if not words:
        return []

    chunks = []
    current: List[str] = []
    current_len = 0

    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunk_str = " ".join(current)
            chunks.append(chunk_str)
            # build overlap: keep trailing words worth ~overlap chars
            overlap_words = []
            overlap_len = 0
            for w in reversed(current):
                overlap_len += len(w) + 1
                overlap_words.insert(0, w)
                if overlap_len >= overlap:
                    break
            current = overlap_words
            current_len = sum(len(w) + 1 for w in current)

    if current:
        chunks.append(" ".join(current))

    # Filter out trivially short trailing chunks
    return [c for c in chunks if len(c) > 20]
