"""BM25 tokenizer for scripture text."""

from __future__ import annotations

import re
import unicodedata

_WORD_BOUNDARY = re.compile(r"\W+")
_PURE_DIGIT = re.compile(r"^\d+$")


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 indexing.

    Pipeline: lowercase -> NFC normalize -> split on word boundaries ->
    drop empties -> drop short pure-digit tokens.

    Args:
        text: Input text to tokenize.

    Returns:
        List of normalized tokens.
    """
    lowered = text.lower()
    normalized = unicodedata.normalize("NFC", lowered)
    raw_tokens = _WORD_BOUNDARY.split(normalized)

    tokens = []
    for tok in raw_tokens:
        if not tok:
            continue
        if _PURE_DIGIT.match(tok) and len(tok) < 2:
            continue
        tokens.append(tok)

    return tokens
