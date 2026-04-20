"""Feedback command for scripvec CLI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Annotated

import typer
from scripvec_retrieval.paths import logs_dir

from .errors import ExitCode, emit_error

app = typer.Typer()


@dataclass(frozen=True)
class FeedbackRecord:
    """A single feedback record."""

    timestamp: str
    schema_version: str
    query_id: str
    verse_id: str
    grade: int
    note: str | None


def _append_feedback(record: FeedbackRecord) -> None:
    """Append feedback record to JSONL file."""
    log_path = logs_dir() / "feedback.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(asdict(record), separators=(",", ":")) + "\n"

    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


@app.command()
def feedback(
    query_id: Annotated[str, typer.Option("--query-id", help="Query ID to provide feedback for")],
    verse_id: Annotated[str, typer.Option("--verse-id", help="Verse ID to rate")],
    grade: Annotated[int, typer.Option("--grade", help="Relevance grade (0, 1, or 2)")],
    note: Annotated[str | None, typer.Option("--note", help="Optional note")] = None,
) -> None:
    """Record relevance feedback for a query result."""
    if grade not in (0, 1, 2):
        emit_error(
            code="INVALID_GRADE",
            message=f"Grade must be 0, 1, or 2, got {grade}",
            exit_code=ExitCode.USER_ERROR,
        )

    record = FeedbackRecord(
        timestamp=datetime.now(UTC).isoformat(),
        schema_version="1",
        query_id=query_id,
        verse_id=verse_id,
        grade=grade,
        note=note,
    )

    _append_feedback(record)

    confirmation = {
        "status": "recorded",
        "query_id": query_id,
        "verse_id": verse_id,
        "grade": grade,
    }
    print(json.dumps(confirmation))
