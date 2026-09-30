"""
Local FAISS-backed vector store, persisted to disk under VECTOR_STORE_DIR.

Each "collection" (e.g. one per user/session) gets its own FAISS index file
plus a JSON sidecar holding the chunk text + metadata for each vector id.
This keeps things simple while still supporting multiple isolated
knowledge bases (so one user's documents don't leak into another's search).
"""
import json
import threading
from pathlib import Path
from typing import List, Dict, Any

import numpy as np

from backend.config import settings
from backend.rag.embeddings import embed_texts, embedding_dim

_lock = threading.Lock()


def _index_path(collection: str) -> Path:
    return settings.VECTOR_STORE_DIR / f"{collection}.index"


def _meta_path(collection: str) -> Path:
    return settings.VECTOR_STORE_DIR / f"{collection}.meta.json"


def _load_meta(collection: str) -> List[Dict[str, Any]]:
    path = _meta_path(collection)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save_meta(collection: str, meta: List[Dict[str, Any]]) -> None:
    _meta_path(collection).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def _load_or_create_index(collection: str):
    import faiss

    path = _index_path(collection)
    dim = embedding_dim()
    if path.exists():
        return faiss.read_index(str(path))
    # Inner product on normalized vectors == cosine similarity
    return faiss.IndexIDMap(faiss.IndexFlatIP(dim))


def _save_index(collection: str, index) -> None:
    import faiss
    faiss.write_index(index, str(_index_path(collection)))


def add_chunks(collection: str, chunks: List[str], document_id: str, filename: str) -> int:
    """
    Embed and add a list of text chunks to the collection's index.
    Returns the number of chunks added.
    """
    if not chunks:
        return 0

    with _lock:
        index = _load_or_create_index(collection)
        meta = _load_meta(collection)

        vectors = embed_texts(chunks)
        start_id = len(meta)
        ids = np.arange(start_id, start_id + len(chunks)).astype("int64")

        index.add_with_ids(vectors, ids)

        for i, chunk in enumerate(chunks):
            meta.append({
                "id": int(start_id + i),
                "text": chunk,
                "document_id": document_id,
                "filename": filename,
            })

        _save_index(collection, index)
        _save_meta(collection, meta)
        return len(chunks)


def search(collection: str, query: str, top_k: int = None) -> List[Dict[str, Any]]:
    """
    Return the top_k most similar chunks to `query` as a list of dicts:
    {text, filename, document_id, score}
    """
    top_k = top_k or settings.TOP_K_CHUNKS
    path = _index_path(collection)
    if not path.exists():
        return []

    with _lock:
        import faiss  # noqa: F401
        index = _load_or_create_index(collection)
        meta = _load_meta(collection)

    if index.ntotal == 0 or not meta:
        return []

    query_vec = embed_texts([query])
    scores, ids = index.search(query_vec, min(top_k, index.ntotal))

    meta_by_id = {m["id"]: m for m in meta}
    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx == -1:
            continue
        m = meta_by_id.get(int(idx))
        if not m:
            continue
        results.append({
            "text": m["text"],
            "filename": m["filename"],
            "document_id": m["document_id"],
            "score": float(score),
        })
    return results


def delete_document(collection: str, document_id: str) -> None:
    """
    Remove all chunks belonging to a document. FAISS doesn't support cheap
    deletion from a flat index, so we rebuild the index from remaining chunks.
    """
    with _lock:
        meta = _load_meta(collection)
        remaining = [m for m in meta if m["document_id"] != document_id]
        if len(remaining) == len(meta):
            return  # nothing to delete

        import faiss
        dim = embedding_dim()
        new_index = faiss.IndexIDMap(faiss.IndexFlatIP(dim))

        if remaining:
            texts = [m["text"] for m in remaining]
            vectors = embed_texts(texts)
            new_ids = np.arange(len(remaining)).astype("int64")
            new_index.add_with_ids(vectors, new_ids)
            for new_id, m in zip(new_ids, remaining):
                m["id"] = int(new_id)

        _save_index(collection, new_index)
        _save_meta(collection, remaining)
