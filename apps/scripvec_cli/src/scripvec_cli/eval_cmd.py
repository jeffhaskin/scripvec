"""Evaluation command for scripvec CLI."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from scripvec_eval.run import EvalReport, run

from .errors import ExitCode, emit_error

app = typer.Typer()


def _format_json(report: EvalReport) -> str:
    """Format report as JSON."""
    data = {
        "index_hash": report.index_hash,
        "metrics": [asdict(m) for m in report.metrics],
        "recall10_by_bucket": report.recall10_by_bucket,
        "ship": asdict(report.ship),
        "failures_path": report.failures_path,
    }
    return json.dumps(data, indent=2)


def _format_text(report: EvalReport) -> str:
    """Format report as ASCII text."""
    lines = []
    lines.append(f"Index: {report.index_hash}")
    lines.append("")
    lines.append("Metrics:")
    hdr = f"{'Mode':<8} {'R@10':>6} {'R@20':>6} {'nDCG':>6} {'MRR':>6} {'p50ms':>7} {'p95ms':>7}"
    lines.append(hdr)
    lines.append("-" * 50)
    for m in report.metrics:
        lines.append(
            f"{m.mode:<8} {m.recall_at_10:>6.3f} {m.recall_at_20:>6.3f} "
            f"{m.ndcg_at_10:>6.3f} {m.mrr_at_10:>6.3f} "
            f"{m.latency_p50_ms:>7.1f} {m.latency_p95_ms:>7.1f}"
        )
    lines.append("")
    lines.append("Recall@10 by Bucket:")
    buckets = set()
    for mode_buckets in report.recall10_by_bucket.values():
        buckets.update(mode_buckets.keys())
    bucket_list = sorted(buckets)
    header = f"{'Mode':<8}" + "".join(f" {b[:8]:>8}" for b in bucket_list)
    lines.append(header)
    lines.append("-" * len(header))
    for mode, buckets_data in report.recall10_by_bucket.items():
        row = f"{mode:<8}"
        for b in bucket_list:
            val = buckets_data.get(b, 0.0)
            row += f" {val:>8.3f}"
        lines.append(row)
    lines.append("")
    lines.append("Ship Criteria:")
    s = report.ship
    h = "PASS" if s.hybrid_beats_bm25_recall10 else "FAIL"
    d = "PASS" if s.dense_beats_bm25_recall10 else "FAIL"
    i = "PASS" if s.index_size_under_400mb else "FAIL"
    lines.append(f"  hybrid > BM25 R@10: {h}")
    lines.append(f"  dense > BM25 R@10:  {d}")
    lines.append(f"  index < 400MB:      {i}")
    lines.append(f"  ALL PASSED: {'YES' if report.ship.all_passed else 'NO'}")
    if report.failures_path:
        lines.append("")
        lines.append(f"Failures written to: {report.failures_path}")
    return "\n".join(lines)


@app.command("run")
def eval_run(
    queries: Annotated[
        Path, typer.Option("--queries", help="Path to queries.jsonl")
    ] = Path("data/eval/queries.jsonl"),
    judgments: Annotated[
        Path, typer.Option("--judgments", help="Path to judgments.jsonl")
    ] = Path("data/eval/judgments.jsonl"),
    index: Annotated[
        str, typer.Option("--index", help="Index hash or 'latest'")
    ] = "latest",
    format_: Annotated[
        str, typer.Option("--format", help="Output format: json or text")
    ] = "json",
) -> None:
    """Run evaluation suite against an index."""
    try:
        report = run(queries, judgments, index=index)
    except RuntimeError as e:
        if "sanity probe" in str(e).lower():
            emit_error(
                code="sanity_probe_failed",
                message=str(e),
                exit_code=ExitCode.USER_ERROR,
            )
        emit_error(
            code="eval_failed",
            message=str(e),
            exit_code=ExitCode.USER_ERROR,
        )
    except (FileNotFoundError, ValueError) as e:
        emit_error(
            code="eval_failed",
            message=str(e),
            exit_code=ExitCode.USER_ERROR,
        )

    if format_ == "text":
        print(_format_text(report))
    else:
        print(_format_json(report))
