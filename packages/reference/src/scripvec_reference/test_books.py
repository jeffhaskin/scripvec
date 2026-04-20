"""Tests for canonical book table."""

import pytest

from scripvec_reference.books import CANONICAL_BOOKS, canonicalize_book


class TestCanonicalBooks:
    def test_bom_books_in_order(self) -> None:
        """BoM books are in canonical order."""
        assert CANONICAL_BOOKS[0] == "1 Nephi"
        assert CANONICAL_BOOKS[14] == "Moroni"

    def test_dandc_last(self) -> None:
        """D&C is the final entry."""
        assert CANONICAL_BOOKS[-1] == "D&C"

    def test_total_count(self) -> None:
        """15 BoM books + 1 D&C = 16 total."""
        assert len(CANONICAL_BOOKS) == 16


class TestCanonicalizeBookPositive:
    @pytest.mark.parametrize("book", CANONICAL_BOOKS)
    def test_every_canonical_book_resolves(self, book: str) -> None:
        """Every canonical book name maps to itself."""
        assert canonicalize_book(book) == book


class TestCanonicalizeBookNegative:
    @pytest.mark.parametrize(
        "invalid",
        [
            "1 Ne",
            "1ne",
            "1 NEPHI",
            "1 nephi",
            "Alm",
            "alma",
            "ALMA",
            "DC",
            "D&c",
            "d&c",
            "D and C",
            "Doctrine and Covenants",
            "Mor",
            "mor",
            "mormon",
            "MORMON",
            "",
            " ",
            "Fake Book",
        ],
    )
    def test_rejects_abbreviations_and_variants(self, invalid: str) -> None:
        """Abbreviations, case variants, and unknown names raise ValueError."""
        with pytest.raises(ValueError, match="Unknown book"):
            canonicalize_book(invalid)
