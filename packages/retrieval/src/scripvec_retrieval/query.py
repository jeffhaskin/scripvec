"""Query path with reference extraction and force-inclusion per ADRs 013/014."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from scripvec_reference.reference import Reference, canonical, extract_references

from .bm25 import bm25_topk, load_bm25
from .config import load_embed_config
from .embed import embed
from .manifest import read_manifest
from .paths import index_path, indexes_dir, resolve_latest
from .rrf import rrf
from .store import dense_topk, get_verse, open_store


@dataclass(frozen=True)
class ResultRow:
    """Single result row with score breakdown and force marker."""

    rank: int
    verse_id: str
    ref: str
    text: str
    score: float
    scores: dict[str, float]
    forced: bool


@dataclass(frozen=True)
class QueryResult:
    """Complete query result with timing and metadata."""

    query: str
    mode: str
    k: int
    index: str
    results: tuple[ResultRow, ...]
    latency_ms: dict[str, float] = field(default_factory=dict)


def _resolve_index(index: str) -> tuple[str, Path]:
    """Resolve index name to (hash, directory path)."""
    if index == "latest":
        hash_hex = resolve_latest()
    else:
        hash_hex = index

    idx_dir = index_path(hash_hex)
    if not idx_dir.is_dir():
        raise FileNotFoundError(f"Index directory not found: {idx_dir}")

    return hash_hex, idx_dir


def _drift_check_endpoint(manifest_endpoint: str, manifest_model: str, manifest_dim: int) -> None:
    """Check for endpoint config drift between manifest and runtime."""
    cfg = load_embed_config()

    mismatches: list[str] = []

    if cfg.base_url != manifest_endpoint:
        mismatches.append(f"base_url: manifest={manifest_endpoint!r}, runtime={cfg.base_url!r}")

    if cfg.model != manifest_model:
        mismatches.append(f"model: manifest={manifest_model!r}, runtime={cfg.model!r}")

    if cfg.dim != manifest_dim:
        mismatches.append(f"dim: manifest={manifest_dim}, runtime={cfg.dim}")

    if mismatches:
        raise RuntimeError(f"Endpoint config drift detected: {'; '.join(mismatches)}")


def _run_bm25(idx_dir: Path, query_text: str, k: int) -> list[tuple[str, float]]:
    """Run BM25 retrieval."""
    bm25_idx = load_bm25(idx_dir)
    return bm25_topk(bm25_idx, query_text, k)


def _run_dense(idx_dir: Path, query_text: str, k: int) -> list[tuple[str, float]]:
    """Run dense retrieval."""
    store = open_store(idx_dir / "corpus.sqlite")
    try:
        query_vec = embed(query_text)
        hits = dense_topk(store, query_vec, k)
        return [(h.verse_id, h.cosine) for h in hits]
    finally:
        store.conn.close()


def query(
    text: str,
    *,
    k: int = 10,
    mode: str = "hybrid",
    index: str = "latest",
) -> QueryResult:
    """Execute a retrieval query with optional reference extraction.

    Args:
        text: Query text.
        k: Number of results to return (may be exceeded by force-inclusion).
        mode: Retrieval mode - "hybrid", "bm25", or "dense".
        index: Index identifier - "latest" or explicit hash.

    Returns:
        QueryResult with results and timing.

    Raises:
        FileNotFoundError: If index doesn't exist.
        RuntimeError: On endpoint drift or other errors.
        ValueError: On invalid mode.
    """
    total_start = time.perf_counter()
    latency: dict[str, float] = {"bm25": 0.0, "dense": 0.0, "fuse": 0.0, "total": 0.0}

    hash_hex, idx_dir = _resolve_index(index)

    manifest = read_manifest(idx_dir / "manifest.json")
    _drift_check_endpoint(manifest.embed_endpoint, manifest.embed_model, manifest.embed_dim)

    extracted_refs = extract_references(text)
    extracted_verse_ids: set[str] = set()

    store = open_store(idx_dir / "corpus.sqlite")
    try:
        for ref in extracted_refs:
            verse_id = _ref_to_verse_id(ref)
            try:
                get_verse(store, verse_id)
                extracted_verse_ids.add(verse_id)
            except KeyError:
                raise RuntimeError(
                    f"Extracted reference {canonical(ref.book, ref.chapter, ref.verse)} "
                    f"does not exist in index"
                )
    finally:
        store.conn.close()

    bm25_hits: list[tuple[str, float]] = []
    dense_hits: list[tuple[str, float]] = []
    fused_hits: list[tuple[str, float]] = []

    if mode == "bm25":
        start = time.perf_counter()
        bm25_hits = _run_bm25(idx_dir, text, k)
        latency["bm25"] = (time.perf_counter() - start) * 1000
        fused_hits = bm25_hits

    elif mode == "dense":
        start = time.perf_counter()
        dense_hits = _run_dense(idx_dir, text, k)
        latency["dense"] = (time.perf_counter() - start) * 1000
        fused_hits = dense_hits

    elif mode == "hybrid":
        start = time.perf_counter()
        bm25_hits = _run_bm25(idx_dir, text, k * 5)
        latency["bm25"] = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        dense_hits = _run_dense(idx_dir, text, k * 5)
        latency["dense"] = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        fused_hits = rrf(bm25_hits, dense_hits, top_k=k)
        latency["fuse"] = (time.perf_counter() - start) * 1000

    else:
        raise ValueError(f"Unknown mode: {mode!r}. Must be 'hybrid', 'bm25', or 'dense'.")

    organic_ids = {vid for vid, _ in fused_hits}

    results: list[ResultRow] = []
    store = open_store(idx_dir / "corpus.sqlite")
    try:
        for ref in extracted_refs:
            verse_id = _ref_to_verse_id(ref)
            if verse_id in extracted_verse_ids:
                verse = get_verse(store, verse_id)
                is_also_organic = verse_id in organic_ids
                results.append(ResultRow(
                    rank=len(results) + 1,
                    verse_id=verse_id,
                    ref=verse.ref_canonical,
                    text=verse.text,
                    score=1.0 if not is_also_organic else _get_score(fused_hits, verse_id),
                    scores={"forced": 1.0},
                    forced=True,
                ))
                if is_also_organic:
                    fused_hits = [(vid, s) for vid, s in fused_hits if vid != verse_id]

        for verse_id, score in fused_hits:
            verse = get_verse(store, verse_id)
            results.append(ResultRow(
                rank=len(results) + 1,
                verse_id=verse_id,
                ref=verse.ref_canonical,
                text=verse.text,
                score=score,
                scores=_build_scores(verse_id, bm25_hits, dense_hits, mode),
                forced=False,
            ))

    finally:
        store.conn.close()

    latency["total"] = (time.perf_counter() - total_start) * 1000

    return QueryResult(
        query=text,
        mode=mode,
        k=k,
        index=hash_hex,
        results=tuple(results),
        latency_ms=latency,
    )


def _ref_to_verse_id(ref: Reference) -> str:
    """Convert Reference to verse_id slug."""
    from scripvec_corpus_ingest.verse import make_verse_id
    return make_verse_id(canonical(ref.book, ref.chapter, ref.verse))


def _get_score(hits: list[tuple[str, float]], verse_id: str) -> float:
    """Get score for verse_id from hits list."""
    for vid, score in hits:
        if vid == verse_id:
            return score
    return 0.0


def _build_scores(
    verse_id: str,
    bm25_hits: list[tuple[str, float]],
    dense_hits: list[tuple[str, float]],
    mode: str,
) -> dict[str, float]:
    """Build scores breakdown dict."""
    scores: dict[str, float] = {}

    if mode in ("bm25", "hybrid"):
        scores["bm25"] = _get_score(bm25_hits, verse_id)

    if mode in ("dense", "hybrid"):
        scores["dense"] = _get_score(dense_hits, verse_id)

    return scores
