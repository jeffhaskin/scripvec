"""Tests for build.py drift guard per CR-001."""

import pytest

from scripvec_retrieval.build import _drift_check_corpus


class TestDriftCheckCorpus:
    def test_no_stored_passes(self) -> None:
        """No stored commit (from-scratch) always passes."""
        _drift_check_corpus(None, "abc123", rebuild_corpus=False)

    def test_match_passes(self) -> None:
        """Matching commits pass."""
        _drift_check_corpus("abc123", "abc123", rebuild_corpus=False)

    def test_mismatch_with_rebuild_passes(self) -> None:
        """Mismatched commits pass with rebuild_corpus=True."""
        _drift_check_corpus("abc123", "def456", rebuild_corpus=True)

    def test_mismatch_raises(self) -> None:
        """Mismatched commits raise with both commits in message."""
        with pytest.raises(RuntimeError) as exc_info:
            _drift_check_corpus("abc123", "def456", rebuild_corpus=False)

        msg = str(exc_info.value)
        assert "abc123" in msg
        assert "def456" in msg
        assert "drift" in msg.lower()
