"""JSON walker for bcbooks corpus (Book of Mormon + Doctrine & Covenants)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterator

from scripvec_corpus_ingest.verse import VerseRecord, make_verse_id


def iter_verses(data_dir: str | Path) -> Iterator[VerseRecord]:
    """Yield all verses from bcbooks corpus in canonical order.

    Order: Book of Mormon books (1 Nephi -> Moroni), then D&C sections.
    """
    data_path = Path(data_dir)
    bcbooks_dir = data_path / "raw" / "bcbooks"

    yield from _iter_book_of_mormon(bcbooks_dir / "book-of-mormon.json")
    yield from _iter_doctrine_and_covenants(bcbooks_dir / "doctrine-and-covenants.json")


def corpus_commit_sha(data_dir: str | Path) -> str:
    """Return git SHA of the commit that last touched data/raw/bcbooks/."""
    data_path = Path(data_dir).resolve()
    bcbooks_dir = data_path / "raw" / "bcbooks"

    if not bcbooks_dir.exists():
        raise FileNotFoundError(f"bcbooks directory not found: {bcbooks_dir}")

    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(bcbooks_dir)],
            capture_output=True,
            text=True,
            check=True,
            cwd=bcbooks_dir,
        )
        sha = result.stdout.strip()
        if not sha:
            raise ValueError(f"No commits touch {bcbooks_dir}")
        return sha
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Not a git repository or git error: {e}") from e


def _iter_book_of_mormon(json_path: Path) -> Iterator[VerseRecord]:
    """Yield verses from Book of Mormon JSON."""
    if not json_path.exists():
        raise FileNotFoundError(f"Book of Mormon JSON not found: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    if "books" not in data:
        raise ValueError(f"Invalid BoM JSON: missing 'books' key in {json_path}")

    for book in data["books"]:
        book_name = book.get("book")
        if not book_name:
            raise ValueError("Invalid BoM JSON: book missing 'book' field")

        for chapter in book.get("chapters", []):
            chapter_num = chapter.get("chapter")
            if chapter_num is None:
                chapter_num = book["chapters"].index(chapter) + 1

            for verse_data in chapter.get("verses", []):
                verse_num = verse_data.get("verse")
                text = verse_data.get("text", "")
                ref = verse_data.get("reference", f"{book_name} {chapter_num}:{verse_num}")

                yield VerseRecord(
                    verse_id=make_verse_id(ref),
                    ref_canonical=ref,
                    book=book_name,
                    chapter=int(chapter_num),
                    verse=int(verse_num),
                    text=text,
                )


def _iter_doctrine_and_covenants(json_path: Path) -> Iterator[VerseRecord]:
    """Yield verses from Doctrine & Covenants JSON."""
    if not json_path.exists():
        raise FileNotFoundError(f"D&C JSON not found: {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    if "sections" not in data:
        raise ValueError(f"Invalid D&C JSON: missing 'sections' key in {json_path}")

    for section in data["sections"]:
        section_num = section.get("section")
        if section_num is None:
            raise ValueError("Invalid D&C JSON: section missing 'section' field")

        for verse_data in section.get("verses", []):
            verse_num = verse_data.get("verse")
            text = verse_data.get("text", "")
            ref = verse_data.get("reference", f"D&C {section_num}:{verse_num}")

            yield VerseRecord(
                verse_id=make_verse_id(ref),
                ref_canonical=ref,
                book="D&C",
                chapter=int(section_num),
                verse=int(verse_num),
                text=text,
            )
