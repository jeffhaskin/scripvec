"""Reciprocal Rank Fusion for hybrid retrieval."""

from __future__ import annotations


def rrf(
    bm25_hits: list[tuple[str, float]],
    dense_hits: list[tuple[str, float]],
    *,
    k: int = 60,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """Fuse BM25 and dense retrieval results using Reciprocal Rank Fusion.

    Args:
        bm25_hits: Ranked list of (verse_id, score) from BM25 retrieval.
        dense_hits: Ranked list of (verse_id, score) from dense retrieval.
        k: RRF smoothing constant (default 60).
        top_k: Number of results to return.

    Returns:
        List of (verse_id, score) tuples sorted by descending score,
        ties broken by verse_id ascending.

    Raises:
        ValueError: If k < 1 or top_k < 1.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")

    scores: dict[str, float] = {}

    for rank, (verse_id, _) in enumerate(bm25_hits, start=1):
        scores[verse_id] = scores.get(verse_id, 0.0) + 1.0 / (k + rank)

    for rank, (verse_id, _) in enumerate(dense_hits, start=1):
        scores[verse_id] = scores.get(verse_id, 0.0) + 1.0 / (k + rank)

    sorted_results = sorted(
        scores.items(),
        key=lambda x: (-x[1], x[0]),
    )

    return sorted_results[:top_k]
