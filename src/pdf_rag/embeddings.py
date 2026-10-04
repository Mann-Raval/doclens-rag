"""Local CPU embeddings shared by documents and queries; no remote API calls."""
from functools import lru_cache
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2


@lru_cache(maxsize=1)
def local_embeddings():
    # Chroma downloads the model on first use and caches its weights on disk.
    return ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
