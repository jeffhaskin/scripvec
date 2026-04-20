"""Tests for VerseRecord and make_verse_id."""

import pytest

from scripvec_corpus_ingest.verse import VerseRecord, make_verse_id


class TestMakeVerseId:
    def test_bom_reference(self) -> None:
        """BoM reference converts to slug."""
        assert make_verse_id("1 Nephi 3:7") == "1-nephi-3-7"

    def test_dandc_reference(self) -> None:
        """D&C reference converts ampersand to 'and'."""
        assert make_verse_id("D&C 88:118") == "dandc-88-118"

    def test_multi_word_book(self) -> None:
        """Multi-word book names convert spaces to hyphens."""
        assert make_verse_id("Words of Mormon 1:1") == "words-of-mormon-1-1"

    def test_lowercase(self) -> None:
        """Output is always lowercase."""
        assert make_verse_id("ALMA 32:21") == "alma-32-21"

    def test_empty_raises(self) -> None:
        """Empty input raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            make_verse_id("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only input raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            make_verse_id("   ")


class TestVerseRecordRoundTrip:
    def test_create_valid_record(self) -> None:
        """Valid VerseRecord can be created."""
        record = VerseRecord(
            verse_id="1-nephi-3-7",
            ref_canonical="1 Nephi 3:7",
            book="1 Nephi",
            chapter=3,
            verse=7,
            text="And it came to pass...",
        )
        assert record.verse_id == "1-nephi-3-7"
        assert record.chapter == 3

    def test_round_trip_via_make_verse_id(self) -> None:
        """make_verse_id output matches VerseRecord verse_id."""
        ref = "Alma 32:21"
        verse_id = make_verse_id(ref)
        record = VerseRecord(
            verse_id=verse_id,
            ref_canonical=ref,
            book="Alma",
            chapter=32,
            verse=21,
            text="Faith is not to have a perfect knowledge...",
        )
        assert record.verse_id == "alma-32-21"


class TestVerseRecordInvariants:
    def test_empty_verse_id_raises(self) -> None:
        with pytest.raises(ValueError, match="verse_id cannot be empty"):
            VerseRecord("", "1 Nephi 1:1", "1 Nephi", 1, 1, "text")

    def test_empty_ref_canonical_raises(self) -> None:
        with pytest.raises(ValueError, match="ref_canonical cannot be empty"):
            VerseRecord("id", "", "1 Nephi", 1, 1, "text")

    def test_empty_book_raises(self) -> None:
        with pytest.raises(ValueError, match="book cannot be empty"):
            VerseRecord("id", "ref", "", 1, 1, "text")

    def test_zero_chapter_raises(self) -> None:
        with pytest.raises(ValueError, match="chapter must be positive"):
            VerseRecord("id", "ref", "book", 0, 1, "text")

    def test_zero_verse_raises(self) -> None:
        with pytest.raises(ValueError, match="verse must be positive"):
            VerseRecord("id", "ref", "book", 1, 0, "text")
