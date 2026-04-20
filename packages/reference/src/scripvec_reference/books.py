"""Canonical book table for Book of Mormon and Doctrine & Covenants."""

from __future__ import annotations

CANONICAL_BOOKS: tuple[str, ...] = (
    "1 Nephi",
    "2 Nephi",
    "Jacob",
    "Enos",
    "Jarom",
    "Omni",
    "Words of Mormon",
    "Mosiah",
    "Alma",
    "Helaman",
    "3 Nephi",
    "4 Nephi",
    "Mormon",
    "Ether",
    "Moroni",
    "D&C",
)

_NAME_TABLE: dict[str, str] = {name: name for name in CANONICAL_BOOKS}


def canonicalize_book(raw: str) -> str:
    """Map book name to canonical form. Raises ValueError on unknown input."""
    canonical = _NAME_TABLE.get(raw)
    if canonical is None:
        raise ValueError(f"Unknown book: {raw!r}")
    return canonical
