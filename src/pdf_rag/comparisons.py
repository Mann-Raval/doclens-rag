"""Bounded discovery of comparison passages across the indexed document text."""
import re

from .config import MAX_SUMMARY_CHUNKS
from .retrieval import _evenly_spaced_chunks, _select_broad_chunks


COMPARISON_CUES = re.compile(
    r"\b(?:differences?|differentiat\w*|compar\w*|versus|vs\.?|whereas|"
    r"unlike|in contrast|on the other hand)\b", re.I
)


def is_comparison_inventory(query: str) -> bool:
    """Distinguish a study inventory from a named pair or PDF-to-PDF comparison."""
    subject = query.split("\nRequested format:", 1)[0].casefold()
    return bool(
        re.search(r"\b(?:all|every)\s+(?:(?:the|important|key)\s+)?(?:differences?|comparisons?)\b", subject)
        and not re.search(r"\bbetween\b|\bversus\b|\bvs\b", subject)
    )


def comparison_passages(chunks):
    """Scan every chunk for cues; prioritize matches then same-file neighbors.

    This is heuristic discovery, not proof that every comparison was found.
    Limit model context without limiting the scan to the first/top ten chunks.
    """
    matched = [i for i, chunk in enumerate(chunks) if COMPARISON_CUES.search(chunk.page_content)]
    selected = _evenly_spaced_chunks(matched, MAX_SUMMARY_CHUNKS)
    positions = set(selected)
    for i in selected:
        for neighbor in (i - 1, i + 1):
            if len(positions) >= MAX_SUMMARY_CHUNKS:
                break
            if 0 <= neighbor < len(chunks) and chunks[neighbor].metadata.get("source") == chunks[i].metadata.get("source"):
                positions.add(neighbor)
    if not positions:
        return _select_broad_chunks(chunks, MAX_SUMMARY_CHUNKS)
    return [chunks[i] for i in sorted(positions)]
