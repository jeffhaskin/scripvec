"""Non-verse text chunker per ADR-009."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

from scripvec_retrieval.embed import _estimate_token_count

# MVP transitional placeholder per ADR-009 § Conflicts
# TODO: Move to project-root config file
_NONVERSE_CHUNK_CAP = 512
_NONVERSE_CHUNK_FLOOR = 768


@dataclass(frozen=True)
class ChunkRecord:
    """Non-verse chunk with same retrieval shape as VerseRecord plus metadata."""

    chunk_id: str
    text: str
    kind: str
    source_id: str
    position: int

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise ValueError("chunk_id cannot be empty")
        if not self.text:
            raise ValueError("text cannot be empty")
        if not self.kind:
            raise ValueError("kind cannot be empty")
        if not self.source_id:
            raise ValueError("source_id cannot be empty")
        if self.position < 0:
            raise ValueError("position must be non-negative")


def _validate_config(cap: int, floor: int) -> None:
    """Validate chunker config invariants per ADR-009."""
    if floor <= cap:
        raise ValueError(
            f"Invariant violated: floor ({floor}) must be > cap ({cap}) per ADR-009"
        )


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using deterministic regex.

    Handles common sentence endings (.!?) followed by whitespace.
    Preserves original text exactly when rejoined.
    """
    pattern = r"(?<=[.!?])\s+"
    parts = re.split(pattern, text.strip())
    return [p for p in parts if p]


def _make_chunk_id(kind: str, source_id: str, position: int) -> str:
    """Generate stable human-readable chunk ID."""
    kind_slug = kind.lower().replace(" ", "-").replace("_", "-")
    source_slug = source_id.lower().replace(" ", "-").replace("_", "-")
    return f"{kind_slug}-{source_slug}-{position}"


def chunk_text(
    text: str,
    kind: str,
    source_id: str,
    *,
    cap: int = _NONVERSE_CHUNK_CAP,
    floor: int = _NONVERSE_CHUNK_FLOOR,
) -> Iterator[ChunkRecord]:
    """Chunk non-verse text per ADR-009 policy.

    Args:
        text: Source text to chunk.
        kind: Type of non-verse content (e.g., "title_page", "testimony").
        source_id: Identifier for the source item.
        cap: Per-chunk token cap (from config).
        floor: No-split floor (from config).

    Yields:
        ChunkRecord for each chunk.

    Raises:
        ValueError: If floor <= cap (invariant violation).
        RuntimeError: If a single sentence exceeds cap (corpus quality bug).
    """
    _validate_config(cap, floor)

    text = text.strip()
    if not text:
        return

    total_tokens = _estimate_token_count(text)

    if total_tokens <= floor:
        yield ChunkRecord(
            chunk_id=_make_chunk_id(kind, source_id, 0),
            text=text,
            kind=kind,
            source_id=source_id,
            position=0,
        )
        return

    sentences = _split_sentences(text)
    if not sentences:
        return

    position = 0
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _estimate_token_count(sentence)

        if sentence_tokens > cap:
            raise RuntimeError(
                f"Single sentence exceeds cap ({sentence_tokens} > {cap}). "
                f"Corpus quality bug per ADR-009. Sentence: {sentence[:100]}..."
            )

        if current_tokens + sentence_tokens > cap and current_chunk:
            chunk_text_joined = " ".join(current_chunk)
            yield ChunkRecord(
                chunk_id=_make_chunk_id(kind, source_id, position),
                text=chunk_text_joined,
                kind=kind,
                source_id=source_id,
                position=position,
            )
            position += 1
            current_chunk = []
            current_tokens = 0

        current_chunk.append(sentence)
        current_tokens += sentence_tokens

    if current_chunk:
        chunk_text_joined = " ".join(current_chunk)
        yield ChunkRecord(
            chunk_id=_make_chunk_id(kind, source_id, position),
            text=chunk_text_joined,
            kind=kind,
            source_id=source_id,
            position=position,
        )
