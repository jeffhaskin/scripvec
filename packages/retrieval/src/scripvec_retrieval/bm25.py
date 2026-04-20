"""BM25S wrapper for scripvec retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import bm25s

from .tokenizer import tokenize

if TYPE_CHECKING:
    from scripvec_corpus_ingest.verse import VerseRecord


@dataclass
class Bm25Index:
    """Opaque wrapper around BM25S retriever with verse_id mapping."""

    _retriever: bm25s.BM25
    _verse_ids: list[str]


def build_bm25(verses: list[VerseRecord], index_dir: Path) -> Bm25Index:
    """Build and persist a BM25 index from verses.

    Args:
        verses: List of VerseRecord objects to index.
        index_dir: Directory to save the index.

    Returns:
        The built Bm25Index.

    Raises:
        ValueError: If corpus is empty.
    """
    if not verses:
        raise ValueError("Cannot build BM25 index from empty corpus")

    verse_ids = [v.verse_id for v in verses]
    corpus_tokens = [tokenize(v.text) for v in verses]

    retriever = bm25s.BM25(k1=1.5, b=0.75)
    retriever.index(corpus_tokens)

    index_dir.mkdir(parents=True, exist_ok=True)
    retriever.save(str(index_dir / "bm25.bm25s"))

    verse_ids_path = index_dir / "verse_ids.json"
    with verse_ids_path.open("w", encoding="utf-8") as f:
        json.dump(verse_ids, f)

    return Bm25Index(_retriever=retriever, _verse_ids=verse_ids)


def load_bm25(index_dir: Path) -> Bm25Index:
    """Load a BM25 index from disk.

    Args:
        index_dir: Directory containing the index.

    Returns:
        The loaded Bm25Index.

    Raises:
        FileNotFoundError: If index files are missing.
        RuntimeError: If index is corrupt or version mismatch.
    """
    bm25_path = index_dir / "bm25.bm25s"
    verse_ids_path = index_dir / "verse_ids.json"

    if not bm25_path.exists():
        raise FileNotFoundError(f"BM25 index not found at {bm25_path}")
    if not verse_ids_path.exists():
        raise FileNotFoundError(f"Verse IDs not found at {verse_ids_path}")

    try:
        retriever = bm25s.BM25.load(str(bm25_path))
    except Exception as e:
        raise RuntimeError(f"Failed to load BM25 index from {bm25_path}: {e}") from e

    try:
        with verse_ids_path.open("r", encoding="utf-8") as f:
            verse_ids = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Corrupt verse_ids.json at {verse_ids_path}: {e}") from e

    if not isinstance(verse_ids, list):
        raise RuntimeError(f"verse_ids.json must be a list, got {type(verse_ids)}")

    return Bm25Index(_retriever=retriever, _verse_ids=verse_ids)


def bm25_topk(idx: Bm25Index, query: str, k: int = 50) -> list[tuple[str, float]]:
    """Retrieve top-k verses by BM25 score.

    Args:
        idx: The BM25 index to query.
        query: Query text.
        k: Number of results to return.

    Returns:
        List of (verse_id, score) tuples sorted by descending score,
        ties broken by verse_id ascending.
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    results, scores = idx._retriever.retrieve([query_tokens], k=min(k, len(idx._verse_ids)))

    if len(results) == 0 or len(results[0]) == 0:
        return []

    doc_indices = results[0]
    doc_scores = scores[0]

    hits: list[tuple[str, float]] = []
    for doc_idx, score in zip(doc_indices, doc_scores, strict=True):
        verse_id = idx._verse_ids[doc_idx]
        hits.append((verse_id, float(score)))

    hits.sort(key=lambda x: (-x[1], x[0]))

    return hits[:k]
