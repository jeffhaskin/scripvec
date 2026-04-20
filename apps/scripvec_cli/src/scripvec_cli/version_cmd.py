"""Version command for scripvec CLI."""

from __future__ import annotations

import json
import sys

import typer

from scripvec_cli.errors import ExitCode, emit_error

CLI_VERSION = "0.0.0"


def _get_version_info() -> dict[str, str | None]:
    """Gather version information, handling missing config/index gracefully."""
    info: dict[str, str | None] = {
        "cli_version": CLI_VERSION,
        "embedding_model": None,
        "latest_index_hash": None,
    }

    try:
        from scripvec_retrieval.config import load_embed_config

        config = load_embed_config()
        info["embedding_model"] = config.model
    except RuntimeError:
        pass

    try:
        from scripvec_retrieval.paths import resolve_latest

        info["latest_index_hash"] = resolve_latest()
    except FileNotFoundError:
        pass

    return info


def version_callback(value: bool) -> None:
    """Handle --version flag."""
    if value:
        info = _get_version_info()
        sys.stdout.write(json.dumps(info) + "\n")
        raise typer.Exit(0)


def version_command() -> None:
    """Show version information as JSON."""
    info = _get_version_info()
    sys.stdout.write(json.dumps(info) + "\n")


def register(app: typer.Typer) -> None:
    """Register version command and --version flag with the app."""
    app.callback(invoke_without_command=True)(
        lambda version: None,
    )

    @app.callback(invoke_without_command=True)
    def main(
        version: bool = typer.Option(
            False,
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version information and exit.",
        ),
    ) -> None:
        """Scripvec CLI - vector search for scripture."""
        pass

    app.command("version")(version_command)
