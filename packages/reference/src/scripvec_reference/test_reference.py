"""Tests for reference parser per ADRs 010-013."""

import pytest

from scripvec_reference.reference import (
    Reference,
    canonical,
    extract_references,
    parse_list,
    parse_range,
    parse_reference,
)


class TestReference:
    def test_valid_reference(self) -> None:
        ref = Reference(book="Alma", chapter=32, verse=21)
        assert ref.book == "Alma"
        assert ref.chapter == 32
        assert ref.verse == 21

    def test_empty_book_raises(self) -> None:
        with pytest.raises(ValueError, match="book cannot be empty"):
            Reference(book="", chapter=1, verse=1)

    def test_zero_chapter_raises(self) -> None:
        with pytest.raises(ValueError, match="chapter must be positive"):
            Reference(book="Alma", chapter=0, verse=1)

    def test_zero_verse_raises(self) -> None:
        with pytest.raises(ValueError, match="verse must be positive"):
            Reference(book="Alma", chapter=1, verse=0)


class TestCanonical:
    def test_round_trip(self) -> None:
        s = canonical("Alma", 32, 21)
        assert s == "Alma 32:21"
        ref = parse_reference(s)
        assert ref.book == "Alma"
        assert ref.chapter == 32
        assert ref.verse == 21


class TestParseReference:
    def test_bom_reference(self) -> None:
        ref = parse_reference("1 Nephi 3:7")
        assert ref.book == "1 Nephi"
        assert ref.chapter == 3
        assert ref.verse == 7

    def test_dandc_reference(self) -> None:
        ref = parse_reference("D&C 88:118")
        assert ref.book == "D&C"
        assert ref.chapter == 88
        assert ref.verse == 118

    def test_whitespace_tolerance(self) -> None:
        ref = parse_reference("  Alma 32:21  ")
        assert ref.book == "Alma"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty reference"):
            parse_reference("")

    def test_unknown_book_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown book"):
            parse_reference("FakeBook 1:1")

    def test_abbreviation_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown book"):
            parse_reference("Alm 32:21")

    def test_case_variant_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown book"):
            parse_reference("alma 32:21")

    def test_leading_zero_chapter_raises(self) -> None:
        with pytest.raises(ValueError, match="Leading zeros"):
            parse_reference("Alma 01:1")

    def test_leading_zero_verse_raises(self) -> None:
        with pytest.raises(ValueError, match="Leading zeros"):
            parse_reference("Alma 1:01")


class TestParseRange:
    def test_valid_range(self) -> None:
        start, end = parse_range("Alma 32:21 - Alma 32:23")
        assert start.verse == 21
        assert end.verse == 23

    def test_cross_chapter_range(self) -> None:
        start, end = parse_range("Alma 32:21 - Alma 33:5")
        assert start.chapter == 32
        assert end.chapter == 33

    def test_cross_book_range(self) -> None:
        start, end = parse_range("Alma 63:17 - Helaman 1:1")
        assert start.book == "Alma"
        assert end.book == "Helaman"

    def test_missing_spaces_raises(self) -> None:
        with pytest.raises(ValueError, match="delimiter"):
            parse_range("Alma 32:21-Alma 32:23")

    def test_reversed_order_raises(self) -> None:
        with pytest.raises(ValueError, match="reversed"):
            parse_range("Alma 32:23 - Alma 32:21")

    def test_shorthand_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_range("Alma 32:21-23")


class TestParseList:
    def test_single_item(self) -> None:
        items = parse_list("Alma 32:21")
        assert len(items) == 1
        assert items[0].verse == 21

    def test_multiple_refs(self) -> None:
        items = parse_list("Alma 32:21; Moroni 7:5")
        assert len(items) == 2

    def test_mixed_refs_and_ranges(self) -> None:
        items = parse_list("Alma 32:21; 1 Nephi 3:7 - 1 Nephi 3:9")
        assert len(items) == 2
        assert isinstance(items[0], Reference)
        assert isinstance(items[1], tuple)

    def test_deduplication(self) -> None:
        items = parse_list("Alma 32:21; Alma 32:21")
        assert len(items) == 1

    def test_malformed_item_names_ordinal(self) -> None:
        with pytest.raises(ValueError, match="Item 2"):
            parse_list("Alma 32:21; FakeBook 1:1")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty list"):
            parse_list("")


class TestExtractReferences:
    def test_single_ref_in_text(self) -> None:
        refs = extract_references("what does Alma 32:21 say about faith")
        assert len(refs) == 1
        assert refs[0].book == "Alma"

    def test_multiple_refs(self) -> None:
        refs = extract_references("compare Alma 32:21 with Moroni 7:5")
        assert len(refs) == 2

    def test_no_refs_returns_empty(self) -> None:
        refs = extract_references("what is faith")
        assert refs == []

    def test_deduplication(self) -> None:
        refs = extract_references("Alma 32:21 and again Alma 32:21")
        assert len(refs) == 1

    def test_partial_match_ignored(self) -> None:
        refs = extract_references("chapter Alma 32 is good")
        assert refs == []

    def test_abbreviation_not_extracted(self) -> None:
        refs = extract_references("see Alm 32:21")
        assert refs == []

    def test_dandc_extraction(self) -> None:
        refs = extract_references("D&C 88:118 says seek learning")
        assert len(refs) == 1
        assert refs[0].book == "D&C"
