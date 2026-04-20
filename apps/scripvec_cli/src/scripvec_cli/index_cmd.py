"""CLI subcommands for index management (build, list)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from scripvec_retrieval.build import build_index
from scripvec_retrieval.manifest import read_manifest
from scripvec_retrieval.paths import indexes_dir, resolve_latest

from .errors import ExitCode, emit_error

app = typer.Typer(no_args_is_help=True)


@app.command("build")
def cmd_build(
    from_scratch: bool = typer.Option(
        True, "--from-scratch/--incremental", help="Build fresh index (incremental not yet supported)"
    ),
    rebuild_corpus: bool = typer.Option(
        False, "--rebuild-corpus", help="Allow corpus drift and rebuild"
    ),
) -> None:
    """Build the search index from corpus.

    Creates vector embeddings and BM25 index for all verses.
    Outputs JSON: {index_hash, latest}
    """
    try:
        hash_hex = build_index(from_scratch=from_scratch, rebuild_corpus=rebuild_corpus)
        result = {"index_hash": hash_hex, "latest": True}
        typer.echo(json.dumps(result))
    except RuntimeError as e:
        msg = str(e)
        if "drift" in msg.lower():
            emit_error("corpus_drift", msg, exit_code=ExitCode.USER_ERROR)
        elif "embed" in msg.lower() or "endpoint" in msg.lower():
            emit_error("embedding_endpoint", msg, exit_code=ExitCode.UPSTREAM_ERROR)
        else:
            emit_error("build_failed", msg, exit_code=ExitCode.USER_ERROR)
    except NotImplementedError as e:
        emit_error("build_failed", str(e), exit_code=ExitCode.USER_ERROR)
    except Exception as e:
        emit_error("build_failed", str(e), exit_code=ExitCode.USER_ERROR)


@app.command("list")
def cmd_list() -> None:
    """List all built indexes.

    Outputs JSON array of {hash, created_at, model, dim, is_latest}
    sorted by hash ascending.
    """
    try:
        idx_dir = indexes_dir()
        if not idx_dir.exists():
            typer.echo("[]")
            return

        try:
            latest_hash = resolve_latest()
        except FileNotFoundError:
            latest_hash = None

        entries: list[dict[str, Any]] = []

        for subdir in idx_dir.iterdir():
            if subdir.name == "latest":
                continue
            if not subdir.is_dir():
                continue

            manifest_path = subdir / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                manifest = read_manifest(manifest_path)
                mtime = manifest_path.stat().st_mtime
                created_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

                entries.append({
                    "hash": subdir.name,
                    "created_at": created_at,
                    "model": manifest.embed_model,
                    "dim": manifest.embed_dim,
                    "is_latest": subdir.name == latest_hash,
                })
            except Exception:
                continue

        entries.sort(key=lambda x: x["hash"])
        typer.echo(json.dumps(entries))

    except Exception as e:
        emit_error("list_failed", str(e), exit_code=ExitCode.USER_ERROR)


def register(parent_app: typer.Typer) -> None:
    """Register the index subcommand with the parent app."""
    parent_app.add_typer(app, name="index")
