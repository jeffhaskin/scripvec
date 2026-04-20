"""Tests for bcbooks corpus walker."""

import pytest

from scripvec_corpus_ingest.bcbooks import corpus_commit_sha, iter_verses


class TestIterVerses:
    def test_yields_verses(self) -> None:
        """iter_verses yields VerseRecord objects."""
        verses = list(iter_verses("data"))
        assert len(verses) > 0

    def test_first_verse_is_1_nephi(self) -> None:
        """First verse is 1 Nephi 1:1."""
        verses = iter(iter_verses("data"))
        first = next(verses)
        assert first.book == "1 Nephi"
        assert first.chapter == 1
        assert first.verse == 1
        assert "Nephi" in first.text

    def test_includes_dandc(self) -> None:
        """D&C verses are included."""
        verses = list(iter_verses("data"))
        dandc_verses = [v for v in verses if v.book == "D&C"]
        assert len(dandc_verses) > 0

    def test_verse_ids_are_slugs(self) -> None:
        """Verse IDs are lowercase slugs."""
        verses = iter(iter_verses("data"))
        first = next(verses)
        assert first.verse_id == "1-nephi-1-1"

    def test_missing_dir_raises(self) -> None:
        """Missing data dir raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            list(iter_verses("/nonexistent/path"))


class TestCorpusCommitSha:
    def test_returns_sha(self) -> None:
        """Returns a 40-char hex SHA."""
        sha = corpus_commit_sha("data")
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)

    def test_missing_dir_raises(self) -> None:
        """Missing bcbooks dir raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            corpus_commit_sha("/nonexistent")
