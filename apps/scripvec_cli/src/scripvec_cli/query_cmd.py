"""CLI command for scripvec query."""

from __future__ import annotations

import json
from enum import Enum
from typing import Annotated

import typer

from scripvec_retrieval.query import QueryResult, query

from . import query_log
from .errors import ExitCode, emit_error


class Mode(str, Enum):
    bm25 = "bm25"
    dense = "dense"
    hybrid = "hybrid"


class Format(str, Enum):
    json = "json"
    text = "text"


_SESSION_ID = query_log.new_session_id()


def _run_query(
    text: str,
    k: int,
    mode: str,
    index: str,
) -> QueryResult:
    """Execute query and return result."""
    return query(text, k=k, mode=mode, index=index)


def _to_log_record(
    result: QueryResult,
    query_id: str,
) -> query_log.QueryLogRecord:
    """Convert QueryResult to log record."""
    log_rows = tuple(
        query_log.ResultLogRow(
            verse_id=r.verse_id,
            bm25_rank=r.scores.get("bm25_rank"),
            dense_rank=r.scores.get("dense_rank"),
            rrf_score=r.score,
        )
        for r in result.results
    )

    return query_log.create_record(
        session_id=_SESSION_ID,
        query_id=query_id,
        index_hash=result.index,
        mode=result.mode,
        query=result.query,
        k=result.k,
        results=log_rows,
        latency_ms=result.latency_ms.get("total", 0.0),
    )


def _format_text(result: QueryResult, show_scores: bool) -> str:
    """Format result as human-readable text."""
    lines = [f"Query: {result.query}", f"Mode: {result.mode}, K: {result.k}, Index: {result.index}", ""]

    for r in result.results:
        forced_marker = " [FORCED]" if r.forced else ""
        score_str = f" (score: {r.score:.4f})" if show_scores else ""
        lines.append(f"{r.rank}. {r.ref}{forced_marker}{score_str}")
        lines.append(f"   {r.text[:100]}..." if len(r.text) > 100 else f"   {r.text}")
        lines.append("")

    return "\n".join(lines)


def _format_json(result: QueryResult, show_scores: bool) -> str:
    """Format result as JSON."""
    data = {
        "query": result.query,
        "mode": result.mode,
        "k": result.k,
        "index": result.index,
        "latency_ms": result.latency_ms,
        "results": [
            {
                "rank": r.rank,
                "verse_id": r.verse_id,
                "ref": r.ref,
                "text": r.text,
                "forced": r.forced,
                **({"score": r.score, "scores": r.scores} if show_scores else {}),
            }
            for r in result.results
        ],
    }
    return json.dumps(data, indent=2)


def cmd_query(
    text: Annotated[str, typer.Argument(help="Query text to search for")],
    k: Annotated[int, typer.Option("--k", "-k", help="Number of results to return")] = 10,
    mode: Annotated[Mode, typer.Option("--mode", "-m", help="Retrieval mode")] = Mode.hybrid,
    format: Annotated[Format, typer.Option("--format", "-f", help="Output format")] = Format.json,
    index: Annotated[str, typer.Option("--index", "-i", help="Index hash or 'latest'")] = "latest",
    show_scores: Annotated[bool, typer.Option("--show-scores", help="Include scores in output")] = False,
) -> None:
    """Search scripture verses using hybrid BM25 + dense retrieval.

    Outputs JSON by default with query results. Appends to queries.jsonl for logging.

    Exit codes:
        0 - Success
        1 - User error (bad flags, build failed)
        2 - Not found (missing index)
        3 - Upstream error (embedding endpoint)

    Example JSON output:
        {
          "query": "faith and works",
          "mode": "hybrid",
          "k": 10,
          "index": "abc123...",
          "results": [{"rank": 1, "verse_id": "...", "ref": "...", "text": "..."}]
        }
    """
    try:
        if k < 1:
            emit_error("bad_flag", f"k must be >= 1, got {k}", exit_code=ExitCode.USER_ERROR)

        result = _run_query(text, k, mode.value, index)

        query_id = query_log.new_query_id()
        log_record = _to_log_record(result, query_id)
        query_log.append(log_record)

        if format == Format.text:
            output = _format_text(result, show_scores)
        else:
            output = _format_json(result, show_scores)

        typer.echo(output)

    except ValueError as e:
        emit_error("bad_flag", str(e), exit_code=ExitCode.USER_ERROR)
    except FileNotFoundError as e:
        emit_error("index_not_found", str(e), exit_code=ExitCode.NOT_FOUND)
    except RuntimeError as e:
        msg = str(e)
        if "drift" in msg.lower():
            emit_error("endpoint_drift", msg, exit_code=ExitCode.UPSTREAM_ERROR)
        elif "embed" in msg.lower() or "endpoint" in msg.lower():
            emit_error("embedding_endpoint", msg, exit_code=ExitCode.UPSTREAM_ERROR)
        else:
            emit_error("query_failed", msg, exit_code=ExitCode.USER_ERROR)


def register(app: typer.Typer) -> None:
    """Register the query command with the parent app."""
    app.command("query")(cmd_query)
