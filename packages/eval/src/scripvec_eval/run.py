"""Evaluation orchestrator and ship criteria for scripvec."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripvec_retrieval.paths import indexes_dir, logs_dir, resolve_latest

from .dataset import Judgment, load_judgments, load_queries, run_sanity_probes
from .metrics import mrr_at_10, ndcg_at_10, percentile, recall_at_k

HYBRID_VS_BM25_PCT = 5
DENSE_VS_BM25_PCT = 5
MAX_INDEX_BYTES = 400 * 1024 * 1024


@dataclass(frozen=True)
class ShipCriteria:
    """Ship criteria evaluation results."""

    hybrid_beats_bm25_recall10: bool
    dense_beats_bm25_recall10: bool
    index_size_under_400mb: bool

    @property
    def all_passed(self) -> bool:
        """Return True if all ship criteria passed."""
        return (
            self.hybrid_beats_bm25_recall10
            and self.dense_beats_bm25_recall10
            and self.index_size_under_400mb
        )


@dataclass(frozen=True)
class ModeMetrics:
    """Metrics for a single retrieval mode."""

    mode: str
    recall_at_10: float
    recall_at_20: float
    ndcg_at_10: float
    mrr_at_10: float
    latency_p50_ms: float
    latency_p95_ms: float


@dataclass(frozen=True)
class FailureRow:
    """A single evaluation failure for logging."""

    query_id: str
    query: str
    mode: str
    expected: list[str]
    retrieved: list[str]
    recall_at_10: float


@dataclass(frozen=True)
class EvalReport:
    """Complete evaluation report."""

    index_hash: str
    metrics: tuple[ModeMetrics, ...]
    recall10_by_bucket: dict[str, dict[str, float]]
    ship: ShipCriteria
    failures_path: str | None


def _index_dir_size_bytes(index_hash: str) -> int:
    """Calculate total size of index directory in bytes."""
    index_path = indexes_dir() / index_hash
    total = 0
    for root, _dirs, files in os.walk(index_path):
        for f in files:
            total += (Path(root) / f).stat().st_size
    return total


def _compute_ship(
    metrics: dict[str, ModeMetrics],
    index_hash: str,
) -> ShipCriteria:
    """Evaluate ship criteria."""
    bm25_recall = metrics["bm25"].recall_at_10
    hybrid_recall = metrics["hybrid"].recall_at_10
    dense_recall = metrics["dense"].recall_at_10

    hybrid_beats = (hybrid_recall - bm25_recall) * 100 >= HYBRID_VS_BM25_PCT
    dense_beats = (dense_recall - bm25_recall) * 100 >= DENSE_VS_BM25_PCT

    index_size = _index_dir_size_bytes(index_hash)
    size_ok = index_size <= MAX_INDEX_BYTES

    return ShipCriteria(
        hybrid_beats_bm25_recall10=hybrid_beats,
        dense_beats_bm25_recall10=dense_beats,
        index_size_under_400mb=size_ok,
    )


def _write_failures(failures: list[FailureRow], index_hash: str) -> str:
    """Write failures to JSONL file and return path."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"failures_{index_hash[:8]}_{timestamp}.jsonl"
    path = logs_dir() / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for failure in failures:
            f.write(json.dumps(asdict(failure), separators=(",", ":")) + "\n")

    return str(path)


def _build_relevant_map(
    judgments: list[Judgment], query_id: str
) -> dict[str, int]:
    """Build relevant doc map for a query."""
    return {j.verse_id: j.grade for j in judgments if j.query_id == query_id}


def run(
    queries_path: Path,
    judgments_path: Path,
    *,
    index: str = "latest",
) -> EvalReport:
    """Run full evaluation suite.

    Args:
        queries_path: Path to queries.jsonl.
        judgments_path: Path to judgments.jsonl.
        index: Index to evaluate ("latest" or explicit hash).

    Returns:
        Complete EvalReport with metrics, stratification, and ship criteria.

    Raises:
        FileNotFoundError: If files or index missing.
        ValueError: On invalid data.
        RuntimeError: On sanity probe failure.
    """
    from scripvec_retrieval.bm25 import load_bm25
    from scripvec_retrieval.query import query as run_query

    index_hash = resolve_latest() if index == "latest" else index
    index_path = indexes_dir() / index_hash

    bm25_idx = load_bm25(index_path)
    known_verse_ids = set(bm25_idx._verse_ids)

    queries = load_queries(queries_path)
    judgments = load_judgments(judgments_path, known_verse_ids)

    run_sanity_probes(bm25_idx)

    modes = ["bm25", "dense", "hybrid"]
    mode_results: dict[str, list[dict]] = {m: [] for m in modes}
    mode_latencies: dict[str, list[float]] = {m: [] for m in modes}
    bucket_recalls: dict[str, dict[str, list[float]]] = {
        m: {} for m in modes
    }
    failures: list[FailureRow] = []

    for q in queries:
        relevant = _build_relevant_map(judgments, q.query_id)

        for mode in modes:
            result = run_query(q.query, k=20, mode=mode, index=index_hash)
            retrieved = [r.verse_id for r in result.results]
            latency = result.latency_ms.get("total", 0.0)

            r10 = recall_at_k(retrieved, relevant, 10)
            r20 = recall_at_k(retrieved, relevant, 20)
            ndcg = ndcg_at_10(retrieved, relevant)
            mrr = mrr_at_10(retrieved, relevant)

            mode_results[mode].append({
                "recall_at_10": r10,
                "recall_at_20": r20,
                "ndcg_at_10": ndcg,
                "mrr_at_10": mrr,
            })
            mode_latencies[mode].append(latency)

            for tag in q.tags:
                if tag not in bucket_recalls[mode]:
                    bucket_recalls[mode][tag] = []
                bucket_recalls[mode][tag].append(r10)

            if r10 < 1.0 and relevant:
                failures.append(FailureRow(
                    query_id=q.query_id,
                    query=q.query,
                    mode=mode,
                    expected=list(relevant.keys()),
                    retrieved=retrieved[:10],
                    recall_at_10=r10,
                ))

    metrics_by_mode: dict[str, ModeMetrics] = {}
    for mode in modes:
        results = mode_results[mode]
        latencies = mode_latencies[mode]

        metrics_by_mode[mode] = ModeMetrics(
            mode=mode,
            recall_at_10=sum(r["recall_at_10"] for r in results) / len(results),
            recall_at_20=sum(r["recall_at_20"] for r in results) / len(results),
            ndcg_at_10=sum(r["ndcg_at_10"] for r in results) / len(results),
            mrr_at_10=sum(r["mrr_at_10"] for r in results) / len(results),
            latency_p50_ms=percentile(latencies, 50) if latencies else 0.0,
            latency_p95_ms=percentile(latencies, 95) if latencies else 0.0,
        )

    recall10_by_bucket: dict[str, dict[str, float]] = {}
    for mode in modes:
        recall10_by_bucket[mode] = {}
        for bucket, recalls in bucket_recalls[mode].items():
            recall10_by_bucket[mode][bucket] = sum(recalls) / len(recalls)

    ship = _compute_ship(metrics_by_mode, index_hash)

    failures_path = None
    if failures:
        failures_path = _write_failures(failures, index_hash)

    return EvalReport(
        index_hash=index_hash,
        metrics=tuple(metrics_by_mode[m] for m in modes),
        recall10_by_bucket=recall10_by_bucket,
        ship=ship,
        failures_path=failures_path,
    )
