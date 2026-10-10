"""Local MiniLM/Chroma retrieval with an optional lexical baseline."""
import math
import os
import uuid
import weakref
import time
from collections import Counter
from dataclasses import dataclass
from threading import Lock
from typing import Callable, Sequence

from langchain_core.documents import Document

from .config import (MAX_SUMMARY_CHUNKS, RETRIEVAL_CHUNKS,
                     RETRIEVAL_CANDIDATES, TOKEN_PATTERN)
from .metrics import log_metrics

_chroma_client_lock = Lock()
_shared_chroma_client = None


@dataclass
class PdfIndex:
    """A session-owned semantic index, or optional TF-IDF baseline."""

    chunks: list[Document]
    idf: dict[str, float]
    vectors: list[dict[str, float]]
    collection: object = None
    _cleanup: object = None

    @classmethod
    def from_documents(
        cls, chunks: list[Document], *, backend=None, embedding_function=None,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> "PdfIndex":
        backend = backend or os.getenv("RETRIEVAL_BACKEND", "semantic")
        if backend == "semantic":
            if not chunks:
                raise ValueError("Cannot index an empty document set.")
            from .embeddings import local_embeddings
            started = time.perf_counter()
            if on_progress:
                on_progress("Preparing embedding model (first use may download weights)", 0, len(chunks))
            client = _chroma_client()
            name = f"doclens_{uuid.uuid4().hex}"
            collection = client.create_collection(
                name=name,
                embedding_function=embedding_function or local_embeddings(),
                metadata={"hnsw:space": "cosine"},
            )
            index = cls(chunks=chunks, idf={}, vectors=[], collection=collection)
            index._cleanup = weakref.finalize(index, _delete_collection, client, name)
            try:
                # Bound embedding batch size to avoid processing every PDF at once.
                for start in range(0, len(chunks), 32):
                    batch = chunks[start:start + 32]
                    collection.add(
                        ids=[str(i) for i in range(start, start + len(batch))],
                        documents=[doc.page_content for doc in batch],
                        metadatas=[{"source": str(doc.metadata.get("source", "Unknown PDF")),
                                    "page": int(doc.metadata.get("page", -1)),
                                    "chunk_id": str(doc.metadata.get("chunk_id", start + i))}
                                   for i, doc in enumerate(batch)],
                    )
                    if on_progress:
                        on_progress("Embedding and indexing passages", min(start + 32, len(chunks)), len(chunks))
            except Exception:
                index.close()
                raise
            log_metrics("index_embeddings", seconds=round(time.perf_counter() - started, 3), chunks=len(chunks))
            return index
        if backend != "lexical":
            raise ValueError("RETRIEVAL_BACKEND must be semantic or lexical.")
        idf, vectors = _build_sparse_index(chunks)
        return cls(chunks=chunks, idf=idf, vectors=vectors)

    def close(self):
        """Release this session's collection on replacement/removal."""
        if self._cleanup and self._cleanup.alive:
            self._cleanup()

    def retrieve(self, query: str, *, broad: bool = False) -> list[Document]:
        if broad:
            return _select_broad_chunks(self.chunks, MAX_SUMMARY_CHUNKS)
        if self.collection is not None:
            result = self.collection.query(
                query_texts=[query], n_results=min(RETRIEVAL_CHUNKS, len(self.chunks)),
                include=["distances"],
            )
            return [self.chunks[int(chunk_id)] for chunk_id in result["ids"][0]]
        query_vector = _vectorize(_terms(query), self.idf)
        if not query_vector:
            return _select_broad_chunks(
                self.chunks, min(RETRIEVAL_CHUNKS, len(self.chunks))
            )
        return _mmr_search(
            self.chunks,
            self.vectors,
            query_vector,
            k=min(RETRIEVAL_CHUNKS, len(self.chunks)),
            candidate_count=min(RETRIEVAL_CANDIDATES, len(self.chunks)),
        )


def _chroma_client():
    """Publish one fully initialized client, even during concurrent cold starts.

    A cached function alone can execute concurrently on its first cache miss.
    Chroma's ephemeral system is process-shared, so serialize construction and
    retain the client for the process lifetime. Sessions delete only collections.
    """
    global _shared_chroma_client
    with _chroma_client_lock:
        if _shared_chroma_client is None:
            import chromadb
            from chromadb.config import Settings
            _shared_chroma_client = chromadb.EphemeralClient(
                settings=Settings(anonymized_telemetry=False)
            )
        return _shared_chroma_client


def _delete_collection(client, name):
    client.delete_collection(name)


def _terms(text: str) -> list[str]:
    """Create word and adjacent-word features for lightweight local search."""
    words = TOKEN_PATTERN.findall(text.casefold())
    bigrams = [f"{left}::{right}" for left, right in zip(words, words[1:])]
    return words + bigrams


def _build_sparse_index(
    documents: Sequence[Document],
) -> tuple[dict[str, float], list[dict[str, float]]]:
    document_terms = [_terms(document.page_content) for document in documents]
    document_frequency: Counter[str] = Counter()
    for terms in document_terms:
        document_frequency.update(set(terms))

    document_count = len(documents)
    idf = {
        term: math.log((document_count + 1) / (frequency + 1)) + 1
        for term, frequency in document_frequency.items()
    }
    vectors = [_vectorize(terms, idf) for terms in document_terms]
    return idf, vectors


def _vectorize(terms: Sequence[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(term for term in terms if term in idf)
    weighted = {
        term: (1 + math.log(count)) * idf[term] for term, count in counts.items()
    }
    magnitude = math.sqrt(sum(value * value for value in weighted.values()))
    if not magnitude:
        return {}
    return {term: value / magnitude for term, value in weighted.items()}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(term, 0.0) for term, value in left.items())


def _mmr_search(
    documents: Sequence[Document],
    vectors: Sequence[dict[str, float]],
    query_vector: dict[str, float],
    *,
    k: int,
    candidate_count: int,
    relevance_weight: float = 0.75,
) -> list[Document]:
    """Balance lexical relevance with diversity among selected passages."""
    relevance = [_cosine(query_vector, vector) for vector in vectors]
    candidates = sorted(
        range(len(documents)), key=lambda index: relevance[index], reverse=True
    )[:candidate_count]
    if not candidates or relevance[candidates[0]] <= 0:
        return _select_broad_chunks(list(documents), k)

    selected: list[int] = []
    while candidates and len(selected) < k:
        best = max(
            candidates,
            key=lambda index: relevance_weight * relevance[index]
            - (1 - relevance_weight)
            * max(
                (_cosine(vectors[index], vectors[chosen]) for chosen in selected),
                default=0.0,
            ),
        )
        selected.append(best)
        candidates.remove(best)
    return [documents[index] for index in selected]
def _evenly_spaced_chunks(chunks: list[Document], limit: int) -> list[Document]:
    """Cover the whole document without overflowing the model context."""
    if limit <= 0 or not chunks:
        return []
    if len(chunks) <= limit:
        return chunks
    if limit == 1:
        return [chunks[len(chunks) // 2]]
    step = (len(chunks) - 1) / (limit - 1)
    return [chunks[round(index * step)] for index in range(limit)]


def _select_broad_chunks(chunks: list[Document], limit: int) -> list[Document]:
    """Sample every PDF so summaries are not dominated by one document."""
    by_source: dict[str, list[Document]] = {}
    for chunk in chunks:
        source = str(chunk.metadata.get("source", "Unknown PDF"))
        by_source.setdefault(source, []).append(chunk)

    if len(chunks) <= limit:
        return chunks

    source_count = len(by_source)
    base_allowance, remainder = divmod(limit, source_count)
    selected: list[Document] = []
    for position, source_chunks in enumerate(by_source.values()):
        allowance = base_allowance + (1 if position < remainder else 0)
        if allowance:
            selected.extend(_evenly_spaced_chunks(source_chunks, allowance))
    return selected
