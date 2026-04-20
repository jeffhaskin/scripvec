"""Query logging for scripvec CLI."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from scripvec_retrieval.paths import logs_dir


@dataclass(frozen=True)
class ResultLogRow:
    """Single result row in query log."""

    verse_id: str
    bm25_rank: int | None
    dense_rank: int | None
    rrf_score: float


@dataclass(frozen=True)
class QueryLogRecord:
    """Record of a single query for logging."""

    timestamp: str
    schema_version: str
    session_id: str
    query_id: str
    index_hash: str
    mode: str
    query: str
    k: int
    results: tuple[ResultLogRow, ...]
    latency_ms: float


def new_session_id() -> str:
    """Generate a new session ID (UUID4 hex)."""
    return uuid.uuid4().hex


def new_query_id() -> str:
    """Generate a new query ID (UUID4 hex)."""
    return uuid.uuid4().hex


def _serialize_record(record: QueryLogRecord) -> str:
    """Serialize a query log record to JSON."""
    data = asdict(record)
    data["results"] = [
        asdict(r) if hasattr(r, "__dataclass_fields__") else r for r in record.results
    ]
    return json.dumps(data, separators=(",", ":"))


def append(record: QueryLogRecord) -> None:
    """Append a query log record to the JSONL file.

    Creates parent directories if absent. Raises on OSError.

    Args:
        record: The query record to append.

    Raises:
        OSError: If the write fails.
    """
    log_path = logs_dir() / "queries.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    line = _serialize_record(record) + "\n"

    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def create_record(
    *,
    session_id: str,
    query_id: str,
    index_hash: str,
    mode: str,
    query: str,
    k: int,
    results: tuple[ResultLogRow, ...],
    latency_ms: float,
) -> QueryLogRecord:
    """Create a query log record with current timestamp."""
    return QueryLogRecord(
        timestamp=datetime.now(UTC).isoformat(),
        schema_version="1",
        session_id=session_id,
        query_id=query_id,
        index_hash=index_hash,
        mode=mode,
        query=query,
        k=k,
        results=results,
        latency_ms=latency_ms,
    )
