"""Reference parser implementing ADRs 010-013."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from scripvec_reference.books import CANONICAL_BOOKS, canonicalize_book


@dataclass(frozen=True)
class Reference:
    """Immutable scriptural reference."""

    book: str
    chapter: int
    verse: int

    def __post_init__(self) -> None:
        if not self.book:
            raise ValueError("book cannot be empty")
        if self.chapter < 1:
            raise ValueError("chapter must be positive")
        if self.verse < 1:
            raise ValueError("verse must be positive")


Range = tuple[Reference, Reference]


def canonical(book: str, chapter: int, verse: int) -> str:
    """Create canonical reference string from components."""
    return f"{book} {chapter}:{verse}"


def _split_book_and_loc(s: str) -> tuple[str, str]:
    """Split reference string into book name and chapter:verse location."""
    s = s.strip()
    match = re.match(r"^(.+?)\s+(\d+:\d+)$", s)
    if not match:
        raise ValueError(f"Invalid reference format: {s!r}")
    return match.group(1), match.group(2)


def parse_reference(s: str) -> Reference:
    """Parse a single canonical reference per ADR-010.

    Format: <canonical_book> <chapter>:<verse>
    - Case-sensitive book name
    - Positive integers without leading zeros
    """
    s = s.strip()
    if not s:
        raise ValueError("Empty reference")

    book_part, loc_part = _split_book_and_loc(s)

    try:
        book = canonicalize_book(book_part)
    except ValueError:
        raise ValueError(f"Unknown book: {book_part!r}")

    chapter_str, verse_str = loc_part.split(":")

    if chapter_str != str(int(chapter_str)):
        raise ValueError(f"Leading zeros not allowed in chapter: {chapter_str!r}")
    if verse_str != str(int(verse_str)):
        raise ValueError(f"Leading zeros not allowed in verse: {verse_str!r}")

    chapter = int(chapter_str)
    verse = int(verse_str)

    if chapter < 1:
        raise ValueError(f"Chapter must be positive: {chapter}")
    if verse < 1:
        raise ValueError(f"Verse must be positive: {verse}")

    return Reference(book=book, chapter=chapter, verse=verse)


def parse_range(s: str) -> Range:
    """Parse a reference range per ADR-011.

    Format: <canonical_ref> - <canonical_ref>
    - ASCII hyphen with spaces on each side
    - Reversed order raises
    """
    s = s.strip()
    if " - " not in s:
        raise ValueError("Range must use ' - ' delimiter (hyphen with spaces)")

    parts = s.split(" - ")
    if len(parts) != 2:
        raise ValueError("Range must have exactly two endpoints")

    start = parse_reference(parts[0])
    end = parse_reference(parts[1])

    if _compare_refs(start, end) > 0:
        raise ValueError("Range endpoints are reversed")

    return (start, end)


def _compare_refs(a: Reference, b: Reference) -> int:
    """Compare two references in canonical document order.

    Returns negative if a < b, zero if equal, positive if a > b.
    """
    book_order_a = CANONICAL_BOOKS.index(a.book) if a.book in CANONICAL_BOOKS else -1
    book_order_b = CANONICAL_BOOKS.index(b.book) if b.book in CANONICAL_BOOKS else -1

    if book_order_a != book_order_b:
        return book_order_a - book_order_b
    if a.chapter != b.chapter:
        return a.chapter - b.chapter
    return a.verse - b.verse


def parse_list(s: str) -> list[Union[Reference, Range]]:
    """Parse a semicolon-separated list of references/ranges per ADR-012.

    - Deduplicates valid duplicates
    - Malformed item raises with 1-based ordinal position
    """
    s = s.strip()
    if not s:
        raise ValueError("Empty list")

    items = [item.strip() for item in s.split(";")]
    results: list[Union[Reference, Range]] = []
    seen: set[tuple[str, int, int]] = set()

    for i, item in enumerate(items, start=1):
        if not item:
            continue

        try:
            if " - " in item:
                parsed = parse_range(item)
                key = (parsed[0].book, parsed[0].chapter, parsed[0].verse,
                       parsed[1].book, parsed[1].chapter, parsed[1].verse)
            else:
                parsed = parse_reference(item)
                key = (parsed.book, parsed.chapter, parsed.verse)

            if key not in seen:
                seen.add(key)
                results.append(parsed)
        except ValueError as e:
            raise ValueError(f"Item {i}: {e}") from e

    return results


_SINGLE_REF_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(book) for book in CANONICAL_BOOKS) + r")\s+(\d+):(\d+)\b"
)


def extract_references(text: str) -> list[Reference]:
    """Extract references from free text per ADR-013.

    - Scans for single refs and ranges
    - Returns empty list if none found (not a raise)
    - Deduplicates in canonical order
    """
    results: list[Reference] = []
    seen: set[tuple[str, int, int]] = set()

    for match in _SINGLE_REF_PATTERN.finditer(text):
        book = match.group(1)
        chapter_str = match.group(2)
        verse_str = match.group(3)

        try:
            if chapter_str != str(int(chapter_str)):
                continue
            if verse_str != str(int(verse_str)):
                continue

            chapter = int(chapter_str)
            verse = int(verse_str)

            if chapter < 1 or verse < 1:
                continue

            ref = Reference(book=book, chapter=chapter, verse=verse)
            key = (ref.book, ref.chapter, ref.verse)

            if key not in seen:
                seen.add(key)
                results.append(ref)
        except (ValueError, IndexError):
            continue

    results.sort(key=lambda r: (CANONICAL_BOOKS.index(r.book), r.chapter, r.verse))
    return results
