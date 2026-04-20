"""VerseRecord dataclass and verse_id slug generation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VerseRecord:
    """Immutable verse record with canonical reference and text."""

    verse_id: str
    ref_canonical: str
    book: str
    chapter: int
    verse: int
    text: str

    def __post_init__(self) -> None:
        if not self.verse_id:
            raise ValueError("verse_id cannot be empty")
        if not self.ref_canonical:
            raise ValueError("ref_canonical cannot be empty")
        if not self.book:
            raise ValueError("book cannot be empty")
        if self.chapter < 1:
            raise ValueError("chapter must be positive")
        if self.verse < 1:
            raise ValueError("verse must be positive")


def make_verse_id(ref_canonical: str) -> str:
    """Generate stable human-readable slug from canonical reference.

    Examples:
        "1 Nephi 3:7" -> "1-nephi-3-7"
        "D&C 88:118" -> "dandc-88-118"
    """
    if not ref_canonical or not ref_canonical.strip():
        raise ValueError("ref_canonical cannot be empty")

    slug = ref_canonical.lower()
    slug = slug.replace("&", "and")
    slug = re.sub(r"[\s:]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug
