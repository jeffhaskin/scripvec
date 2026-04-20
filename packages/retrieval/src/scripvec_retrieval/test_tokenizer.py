"""Tests for BM25 tokenizer."""

from scripvec_retrieval.tokenizer import tokenize


class TestLowercasing:
    """Test lowercase normalization."""

    def test_uppercase_to_lowercase(self) -> None:
        """Uppercase letters converted to lowercase."""
        assert tokenize("HELLO WORLD") == ["hello", "world"]

    def test_mixed_case(self) -> None:
        """Mixed case normalized to lowercase."""
        assert tokenize("HeLLo WoRLd") == ["hello", "world"]

    def test_already_lowercase(self) -> None:
        """Already lowercase text unchanged."""
        assert tokenize("hello world") == ["hello", "world"]


class TestNFCNormalization:
    """Test Unicode NFC normalization."""

    def test_composed_characters(self) -> None:
        """Decomposed characters normalized to composed form."""
        decomposed = "cafe\u0301"  # cafe + combining acute
        composed = "caf\u00e9"  # cafe with e-acute
        result = tokenize(decomposed)
        expected = tokenize(composed)
        assert result == expected

    def test_nfc_deterministic(self) -> None:
        """NFC normalization produces consistent results."""
        text = "na\u00efve"  # naive with diaeresis
        assert tokenize(text) == tokenize(text)


class TestWordBoundarySplit:
    """Test splitting on word boundaries."""

    def test_space_split(self) -> None:
        """Spaces split tokens."""
        assert tokenize("hello world") == ["hello", "world"]

    def test_punctuation_split(self) -> None:
        """Punctuation splits tokens."""
        assert tokenize("hello, world!") == ["hello", "world"]

    def test_multiple_punctuation(self) -> None:
        """Multiple punctuation marks handled."""
        assert tokenize("hello... world!!!") == ["hello", "world"]

    def test_hyphen_split(self) -> None:
        """Hyphens split tokens."""
        assert tokenize("self-evident") == ["self", "evident"]

    def test_colon_split(self) -> None:
        """Colons split tokens (scripture references)."""
        assert tokenize("10:16") == ["10", "16"]


class TestDropShortDigitTokens:
    """Test dropping pure-digit tokens < 2 chars."""

    def test_single_digit_dropped(self) -> None:
        """Single digit tokens dropped."""
        assert tokenize("verse 3") == ["verse"]

    def test_two_digit_kept(self) -> None:
        """Two digit tokens kept."""
        assert tokenize("verse 16") == ["verse", "16"]

    def test_three_digit_kept(self) -> None:
        """Three+ digit tokens kept."""
        assert tokenize("year 1830") == ["year", "1830"]

    def test_mixed_alphanumeric_kept(self) -> None:
        """Alphanumeric tokens not affected by digit rule."""
        assert tokenize("chapter3") == ["chapter3"]

    def test_digit_with_letter_kept(self) -> None:
        """Tokens with any letter kept regardless of digits."""
        assert tokenize("3rd") == ["3rd"]


class TestKeepAlphanumerics:
    """Test that alphanumeric tokens are preserved."""

    def test_letters_preserved(self) -> None:
        """Pure letter tokens preserved."""
        assert tokenize("nephi moroni") == ["nephi", "moroni"]

    def test_numbers_two_plus_preserved(self) -> None:
        """Numbers with 2+ digits preserved."""
        assert tokenize("88 118") == ["88", "118"]

    def test_alphanumeric_mix_preserved(self) -> None:
        """Mixed alphanumeric tokens preserved."""
        assert tokenize("1nephi 2nephi") == ["1nephi", "2nephi"]


class TestDeterminism:
    """Test deterministic output."""

    def test_repeated_calls_same_result(self) -> None:
        """Multiple calls produce identical output."""
        text = "And it came to pass that Nephi went forth"
        result1 = tokenize(text)
        result2 = tokenize(text)
        assert result1 == result2

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        assert tokenize("") == []

    def test_whitespace_only(self) -> None:
        """Whitespace-only returns empty list."""
        assert tokenize("   \t\n  ") == []
