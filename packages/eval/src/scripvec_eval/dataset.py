"""Dataset loaders and sanity probes for scripvec evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripvec_retrieval.bm25 import Bm25Index


CANONICAL_BUCKETS = frozenset({"doctrinal", "narrative", "phrase-memory", "proper-noun"})


@dataclass(frozen=True)
class QueryRow:
    """A single query from the evaluation dataset."""

    query_id: str
    query: str
    tags: tuple[str, ...]
    notes: str | None = None


@dataclass(frozen=True)
class Judgment:
    """A relevance judgment for a query-verse pair."""

    query_id: str
    verse_id: str
    grade: int


@dataclass(frozen=True)
class SanityProbe:
    """A sanity check probe for BM25 retrieval."""

    query: str
    expected_top3: tuple[str, ...]


SANITY_PROBES: tuple[SanityProbe, ...] = (
    SanityProbe(
        query="I will go and do the things which the Lord hath commanded",
        expected_top3=("1-nephi-3-7",),
    ),
    SanityProbe(
        query="seek learning even by study and also by faith",
        expected_top3=("dandc-88-118",),
    ),
    SanityProbe(
        query="faith is not to have a perfect knowledge of things",
        expected_top3=("alma-32-21",),
    ),
)


def _parse_query_row(line: str, line_num: int) -> QueryRow:
    """Parse a single query JSONL line."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON at line {line_num}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Line {line_num}: expected object, got {type(data).__name__}")

    required = {"query_id", "query", "tags"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Line {line_num}: missing required fields: {missing}")

    if not isinstance(data["tags"], list):
        raise ValueError(f"Line {line_num}: 'tags' must be a list")

    return QueryRow(
        query_id=str(data["query_id"]),
        query=str(data["query"]),
        tags=tuple(str(t) for t in data["tags"]),
        notes=data.get("notes"),
    )


def _parse_judgment_row(
    line: str, line_num: int, known_verse_ids: set[str]
) -> Judgment:
    """Parse a single judgment JSONL line."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON at line {line_num}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Line {line_num}: expected object, got {type(data).__name__}")

    required = {"query_id", "verse_id", "grade"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Line {line_num}: missing required fields: {missing}")

    verse_id = str(data["verse_id"])
    if verse_id not in known_verse_ids:
        raise ValueError(f"Line {line_num}: unknown verse_id: {verse_id}")

    grade = data["grade"]
    if not isinstance(grade, int) or grade not in (1, 2):
        raise ValueError(f"Line {line_num}: grade must be 1 or 2, got {grade}")

    return Judgment(
        query_id=str(data["query_id"]),
        verse_id=verse_id,
        grade=grade,
    )


def load_queries(path: Path) -> list[QueryRow]:
    """Load queries from JSONL file.

    Args:
        path: Path to queries.jsonl file.

    Returns:
        List of QueryRow objects.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: On duplicate query_id/text, malformed row, or <8 per bucket.
    """
    if not path.exists():
        raise FileNotFoundError(f"Queries file not found: {path}")

    queries: list[QueryRow] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    bucket_counts: dict[str, int] = {b: 0 for b in CANONICAL_BUCKETS}

    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            row = _parse_query_row(line, line_num)

            if row.query_id in seen_ids:
                raise ValueError(f"Line {line_num}: duplicate query_id: {row.query_id}")
            if row.query in seen_texts:
                raise ValueError(f"Line {line_num}: duplicate query text: {row.query!r}")

            seen_ids.add(row.query_id)
            seen_texts.add(row.query)

            for tag in row.tags:
                if tag in bucket_counts:
                    bucket_counts[tag] += 1

            queries.append(row)

    for bucket, count in bucket_counts.items():
        if count < 8:
            raise ValueError(
                f"Bucket '{bucket}' has only {count} queries, minimum is 8"
            )

    return queries


def load_judgments(path: Path, known_verse_ids: set[str]) -> list[Judgment]:
    """Load relevance judgments from JSONL file.

    Args:
        path: Path to judgments.jsonl file.
        known_verse_ids: Set of valid verse IDs from the corpus.

    Returns:
        List of Judgment objects.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: On unknown verse_id, invalid grade, or malformed row.
    """
    if not path.exists():
        raise FileNotFoundError(f"Judgments file not found: {path}")

    judgments: list[Judgment] = []

    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            judgment = _parse_judgment_row(line, line_num, known_verse_ids)
            judgments.append(judgment)

    return judgments


def run_sanity_probes(idx: Bm25Index) -> None:
    """Run sanity probes against a BM25 index.

    Args:
        idx: The BM25 index to test.

    Raises:
        RuntimeError: If any probe's expected verses don't appear in top-3.
    """
    from scripvec_retrieval.bm25 import bm25_topk

    for probe in SANITY_PROBES:
        results = bm25_topk(idx, probe.query, k=3)
        retrieved_ids = {verse_id for verse_id, _ in results}

        for expected in probe.expected_top3:
            if expected not in retrieved_ids:
                raise RuntimeError(
                    f"Sanity probe failed: query {probe.query!r} "
                    f"expected {expected!r} in top-3, got {retrieved_ids}"
                )
