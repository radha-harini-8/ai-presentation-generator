"""
Thin wrapper around sentence-transformers so the model is loaded only once
(it's relatively expensive to load) and the rest of the app doesn't need to
know which embedding library is being used.
"""
from functools import lru_cache
from typing import List

import numpy as np

from backend.config import settings


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_texts(texts: List[str]) -> np.ndarray:
    """Return an (N, D) float32 numpy array of embeddings for a list of strings."""
    if not texts:
        return np.zeros((0, embedding_dim()), dtype="float32")
    model = _get_model()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vectors.astype("float32")


def embed_query(query: str) -> np.ndarray:
    return embed_texts([query])[0]


@lru_cache(maxsize=1)
def embedding_dim() -> int:
    model = _get_model()
    return model.get_sentence_embedding_dimension()
