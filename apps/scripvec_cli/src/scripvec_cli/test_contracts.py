"""ADR-007 contract tests for CLI subcommands."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from .main import app

runner = CliRunner()


class TestVersion:
    def test_version_json_schema(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "cli_version" in data
        assert "embedding_model" in data

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0


class TestFeedback:
    def test_feedback_bad_grade_error(self) -> None:
        result = runner.invoke(
            app,
            ["feedback", "feedback", "--query-id", "test", "--verse-id", "test", "--grade", "5"],
        )
        assert result.exit_code != 0


class TestIndexList:
    def test_index_list_empty_array(self) -> None:
        result = runner.invoke(app, ["index", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestQuery:
    def test_query_bad_k_structured_error(self) -> None:
        result = runner.invoke(app, ["query", "test", "--k", "0"])
        assert result.exit_code != 0

    def test_query_missing_index_error(self) -> None:
        result = runner.invoke(app, ["query", "test", "--index", "nonexistent"])
        assert result.exit_code != 0
