"""
High-level retrieval helper used by the AI generation pipeline.
Converts a topic/query into relevant chunks pulled from the vector store.
"""
from typing import List, Dict, Any

from backend.rag import vector_store


def retrieve_context(collection: str, query: str, top_k: int = None) -> List[Dict[str, Any]]:
    """Return relevant chunks for `query` from the given collection."""
    return vector_store.search(collection, query, top_k=top_k)


def format_context_for_prompt(chunks: List[Dict[str, Any]], max_chars: int = 6000) -> str:
    """
    Turn retrieved chunks into a compact, source-attributed text block
    suitable for inserting into a Gemini prompt.
    """
    if not chunks:
        return "(No source documents were retrieved for this topic.)"

    parts = []
    total = 0
    for chunk in chunks:
        snippet = f"[Source: {chunk['filename']}]\n{chunk['text']}\n"
        if total + len(snippet) > max_chars:
            break
        parts.append(snippet)
        total += len(snippet)

    return "\n---\n".join(parts)
