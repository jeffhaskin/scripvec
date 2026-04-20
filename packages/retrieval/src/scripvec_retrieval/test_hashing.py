"""Tests for canonical_json and blake2b_128_hex."""

from scripvec_retrieval.hashing import blake2b_128_hex, canonical_json


class TestCanonicalJson:
    def test_sorted_keys(self) -> None:
        """Keys are sorted regardless of insertion order."""
        obj1 = {"b": 1, "a": 2}
        obj2 = {"a": 2, "b": 1}
        assert canonical_json(obj1) == canonical_json(obj2)

    def test_no_whitespace(self) -> None:
        """Output has no spaces or newlines."""
        obj = {"key": "value", "nested": {"inner": [1, 2, 3]}}
        result = canonical_json(obj)
        assert b" " not in result
        assert b"\n" not in result

    def test_utf8_round_trip(self) -> None:
        """Unicode characters are preserved in UTF-8."""
        obj = {"text": "café ñ 日本語"}
        result = canonical_json(obj)
        assert "café ñ 日本語".encode("utf-8") in result

    def test_deterministic(self) -> None:
        """Same input always produces same output."""
        obj = {"x": [1, 2], "y": {"z": True}}
        results = [canonical_json(obj) for _ in range(10)]
        assert all(r == results[0] for r in results)


class TestBlake2b128Hex:
    def test_32_char_length(self) -> None:
        """Output is exactly 32 hex characters."""
        result = blake2b_128_hex(b"test payload")
        assert len(result) == 32

    def test_lowercase_hex(self) -> None:
        """Output is lowercase hex."""
        result = blake2b_128_hex(b"test")
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self) -> None:
        """Same input always produces same hash."""
        payload = b"deterministic input"
        results = [blake2b_128_hex(payload) for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_different_inputs_different_hashes(self) -> None:
        """Different inputs produce different hashes."""
        h1 = blake2b_128_hex(b"input one")
        h2 = blake2b_128_hex(b"input two")
        assert h1 != h2


class TestComposition:
    def test_canonical_json_to_hash_invariant(self) -> None:
        """canonical_json -> blake2b_128_hex is deterministic for equivalent objects."""
        obj1 = {"b": 1, "a": 2, "c": [3, 4]}
        obj2 = {"a": 2, "c": [3, 4], "b": 1}
        h1 = blake2b_128_hex(canonical_json(obj1))
        h2 = blake2b_128_hex(canonical_json(obj2))
        assert h1 == h2
