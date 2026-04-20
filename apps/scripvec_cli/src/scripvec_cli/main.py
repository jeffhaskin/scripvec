"""Scripvec CLI entry point."""

from __future__ import annotations

import typer

from . import eval_cmd, feedback_cmd, index_cmd, query_cmd, version_cmd

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    no_args_is_help=True,
)

query_cmd.register(app)
index_cmd.register(app)
version_cmd.register(app)

app.add_typer(eval_cmd.app, name="eval")
app.add_typer(feedback_cmd.app, name="feedback")
