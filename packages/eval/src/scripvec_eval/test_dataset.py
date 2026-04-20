"""Tests for dataset loaders and sanity probes."""

import json
from pathlib import Path

import pytest

from scripvec_eval.dataset import (
    Judgment,
    QueryRow,
    load_judgments,
    load_queries,
)


class TestLoadQueriesWellFormed:
    """Test load_queries with valid input."""

    def test_loads_valid_queries(self, tmp_path: Path) -> None:
        """Valid JSONL file loads correctly."""
        queries_file = tmp_path / "queries.jsonl"
        queries = [
            {"query_id": f"q{i}", "query": f"query {i}", "tags": ["doctrinal"]}
            for i in range(8)
        ] + [
            {"query_id": f"n{i}", "query": f"narrative {i}", "tags": ["narrative"]}
            for i in range(8)
        ] + [
            {"query_id": f"p{i}", "query": f"phrase {i}", "tags": ["phrase-memory"]}
            for i in range(8)
        ] + [
            {"query_id": f"pn{i}", "query": f"proper {i}", "tags": ["proper-noun"]}
            for i in range(8)
        ]
        queries_file.write_text("\n".join(json.dumps(q) for q in queries))

        result = load_queries(queries_file)
        assert len(result) == 32
        assert all(isinstance(r, QueryRow) for r in result)

    def test_preserves_notes_field(self, tmp_path: Path) -> None:
        """Optional notes field is preserved."""
        queries_file = tmp_path / "queries.jsonl"
        queries = [
            {"query_id": f"q{i}", "query": f"query {i}", "tags": ["doctrinal"], "notes": "note"}
            for i in range(8)
        ] + [
            {"query_id": f"n{i}", "query": f"narrative {i}", "tags": ["narrative"]}
            for i in range(8)
        ] + [
            {"query_id": f"p{i}", "query": f"phrase {i}", "tags": ["phrase-memory"]}
            for i in range(8)
        ] + [
            {"query_id": f"pn{i}", "query": f"proper {i}", "tags": ["proper-noun"]}
            for i in range(8)
        ]
        queries_file.write_text("\n".join(json.dumps(q) for q in queries))

        result = load_queries(queries_file)
        assert result[0].notes == "note"
        assert result[8].notes is None


class TestLoadQueriesDuplicates:
    """Test duplicate detection in load_queries."""

    def test_duplicate_query_id_raises(self, tmp_path: Path) -> None:
        """Duplicate query_id raises ValueError."""
        queries_file = tmp_path / "queries.jsonl"
        queries = [
            {"query_id": "q1", "query": "first query", "tags": ["doctrinal"]},
            {"query_id": "q1", "query": "second query", "tags": ["doctrinal"]},
        ]
        queries_file.write_text("\n".join(json.dumps(q) for q in queries))

        with pytest.raises(ValueError, match="duplicate query_id"):
            load_queries(queries_file)

    def test_duplicate_query_text_raises(self, tmp_path: Path) -> None:
        """Duplicate query text raises ValueError."""
        queries_file = tmp_path / "queries.jsonl"
        queries = [
            {"query_id": "q1", "query": "same query", "tags": ["doctrinal"]},
            {"query_id": "q2", "query": "same query", "tags": ["doctrinal"]},
        ]
        queries_file.write_text("\n".join(json.dumps(q) for q in queries))

        with pytest.raises(ValueError, match="duplicate query text"):
            load_queries(queries_file)


class TestLoadQueriesMalformed:
    """Test malformed input handling in load_queries."""

    def test_malformed_json_raises_with_line_number(self, tmp_path: Path) -> None:
        """Malformed JSON raises ValueError with line number."""
        queries_file = tmp_path / "queries.jsonl"
        line1 = '{"query_id": "q1", "query": "valid", "tags": ["doctrinal"]}'
        queries_file.write_text(f'{line1}\n{{invalid json\n')

        with pytest.raises(ValueError, match="line 2"):
            load_queries(queries_file)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        """Missing required field raises ValueError."""
        queries_file = tmp_path / "queries.jsonl"
        queries_file.write_text('{"query_id": "q1", "query": "test"}\n')

        with pytest.raises(ValueError, match="missing required fields"):
            load_queries(queries_file)

    def test_non_object_raises(self, tmp_path: Path) -> None:
        """Non-object JSON raises ValueError."""
        queries_file = tmp_path / "queries.jsonl"
        queries_file.write_text('["array", "not", "object"]\n')

        with pytest.raises(ValueError, match="expected object"):
            load_queries(queries_file)


class TestLoadQueriesBucketMinimum:
    """Test bucket minimum enforcement in load_queries."""

    def test_under_8_per_bucket_raises(self, tmp_path: Path) -> None:
        """Fewer than 8 queries per bucket raises ValueError."""
        queries_file = tmp_path / "queries.jsonl"
        queries = [
            {"query_id": f"q{i}", "query": f"query {i}", "tags": ["doctrinal"]}
            for i in range(7)  # Only 7, need 8
        ] + [
            {"query_id": f"n{i}", "query": f"narrative {i}", "tags": ["narrative"]}
            for i in range(8)
        ] + [
            {"query_id": f"p{i}", "query": f"phrase {i}", "tags": ["phrase-memory"]}
            for i in range(8)
        ] + [
            {"query_id": f"pn{i}", "query": f"proper {i}", "tags": ["proper-noun"]}
            for i in range(8)
        ]
        queries_file.write_text("\n".join(json.dumps(q) for q in queries))

        with pytest.raises(ValueError, match=r"doctrinal.*has only 7"):
            load_queries(queries_file)


class TestLoadJudgmentsWellFormed:
    """Test load_judgments with valid input."""

    def test_loads_valid_judgments(self, tmp_path: Path) -> None:
        """Valid JSONL file loads correctly."""
        judgments_file = tmp_path / "judgments.jsonl"
        judgments = [
            {"query_id": "q1", "verse_id": "verse-a", "grade": 1},
            {"query_id": "q1", "verse_id": "verse-b", "grade": 2},
        ]
        judgments_file.write_text("\n".join(json.dumps(j) for j in judgments))

        known = {"verse-a", "verse-b", "verse-c"}
        result = load_judgments(judgments_file, known)

        assert len(result) == 2
        assert all(isinstance(r, Judgment) for r in result)
        assert result[0].grade == 1
        assert result[1].grade == 2


class TestLoadJudgmentsUnknownVerse:
    """Test unknown verse_id detection in load_judgments."""

    def test_unknown_verse_id_raises(self, tmp_path: Path) -> None:
        """Unknown verse_id raises ValueError."""
        judgments_file = tmp_path / "judgments.jsonl"
        judgments_file.write_text(
            '{"query_id": "q1", "verse_id": "unknown-verse", "grade": 1}\n'
        )

        known = {"verse-a", "verse-b"}
        with pytest.raises(ValueError, match=r"unknown verse_id.*unknown-verse"):
            load_judgments(judgments_file, known)


class TestLoadJudgmentsInvalidGrade:
    """Test invalid grade detection in load_judgments."""

    def test_grade_zero_raises(self, tmp_path: Path) -> None:
        """Grade 0 raises ValueError."""
        judgments_file = tmp_path / "judgments.jsonl"
        judgments_file.write_text(
            '{"query_id": "q1", "verse_id": "verse-a", "grade": 0}\n'
        )

        known = {"verse-a"}
        with pytest.raises(ValueError, match=r"grade must be 1 or 2.*got 0"):
            load_judgments(judgments_file, known)

    def test_grade_three_raises(self, tmp_path: Path) -> None:
        """Grade 3 raises ValueError."""
        judgments_file = tmp_path / "judgments.jsonl"
        judgments_file.write_text(
            '{"query_id": "q1", "verse_id": "verse-a", "grade": 3}\n'
        )

        known = {"verse-a"}
        with pytest.raises(ValueError, match=r"grade must be 1 or 2.*got 3"):
            load_judgments(judgments_file, known)


class TestLoadJudgmentsMalformed:
    """Test malformed input handling in load_judgments."""

    def test_malformed_json_raises_with_line_number(self, tmp_path: Path) -> None:
        """Malformed JSON raises ValueError with line number."""
        judgments_file = tmp_path / "judgments.jsonl"
        line1 = '{"valid": true, "verse_id": "v", "query_id": "q", "grade": 1}'
        judgments_file.write_text(f"{line1}\n{{bad\n")

        known = {"v"}
        with pytest.raises(ValueError, match="line 2"):
            load_judgments(judgments_file, known)
