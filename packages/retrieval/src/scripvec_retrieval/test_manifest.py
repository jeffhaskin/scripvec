"""Tests for manifest.py — round-trip, missing/extra fields, type mismatches."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from .manifest import Manifest, config_hash, read_manifest, write_manifest


def _sample_manifest() -> Manifest:
    return Manifest(
        corpus_source="bcbooks",
        corpus_commit_sha="abc123def456",
        tokenizer_version=1,
        embed_endpoint="https://api.openai.com/v1",
        embed_model="text-embedding-3-small",
        embed_dim=1536,
        embed_normalized=True,
        bm25_lib="bm25s",
        bm25_lib_version="0.2.0",
        bm25_k1=1.2,
        bm25_b=0.75,
        vec_schema_version=1,
        nonverse_chunk_cap=512,
        nonverse_chunk_floor=64,
    )


class TestRoundTrip:
    def test_write_then_read_recovers_manifest(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        recovered = read_manifest(path)
        assert recovered == m

    def test_config_hash_deterministic(self) -> None:
        m = _sample_manifest()
        h1 = config_hash(m)
        h2 = config_hash(m)
        assert h1 == h2
        assert len(h1) == 32

    def test_config_hash_changes_with_field(self) -> None:
        m1 = _sample_manifest()
        m2 = Manifest(
            corpus_source="bcbooks",
            corpus_commit_sha="different_sha",
            tokenizer_version=1,
            embed_endpoint="https://api.openai.com/v1",
            embed_model="text-embedding-3-small",
            embed_dim=1536,
            embed_normalized=True,
            bm25_lib="bm25s",
            bm25_lib_version="0.2.0",
            bm25_k1=1.2,
            bm25_b=0.75,
            vec_schema_version=1,
            nonverse_chunk_cap=512,
            nonverse_chunk_floor=64,
        )
        assert config_hash(m1) != config_hash(m2)


class TestMissingFields:
    def test_missing_single_field_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        data = {
            "corpus_source": "bcbooks",
            "corpus_commit_sha": "abc123",
            "tokenizer_version": 1,
            "embed_endpoint": "https://api.openai.com/v1",
            "embed_model": "text-embedding-3-small",
            "embed_dim": 1536,
            "embed_normalized": True,
            "bm25_lib": "bm25s",
            "bm25_lib_version": "0.2.0",
            "bm25_k1": 1.2,
            "bm25_b": 0.75,
            "vec_schema_version": 1,
            "nonverse_chunk_cap": 512,
            # missing nonverse_chunk_floor
        }
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="Missing required manifest fields"):
            read_manifest(path)

    def test_missing_multiple_fields_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        data = {"corpus_source": "bcbooks"}
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="Missing required manifest fields"):
            read_manifest(path)


class TestUnknownFields:
    def test_extra_field_raises(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        data = json.loads(path.read_text())
        data["unknown_field"] = "surprise"
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="Unknown manifest fields"):
            read_manifest(path)


class TestTypeMismatch:
    def test_string_where_int_expected_raises(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        data = json.loads(path.read_text())
        data["embed_dim"] = "not_an_int"
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="must be int"):
            read_manifest(path)

    def test_int_where_string_expected_raises(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        data = json.loads(path.read_text())
        data["corpus_source"] = 123
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="must be str"):
            read_manifest(path)

    def test_string_where_bool_expected_raises(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        data = json.loads(path.read_text())
        data["embed_normalized"] = "true"
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="must be bool"):
            read_manifest(path)

    def test_bool_where_int_expected_raises(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        data = json.loads(path.read_text())
        data["embed_dim"] = True
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="must be int"):
            read_manifest(path)

    def test_bool_where_float_expected_raises(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        data = json.loads(path.read_text())
        data["bm25_k1"] = True
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="must be float"):
            read_manifest(path)

    def test_int_accepted_as_float(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "manifest.json"
        write_manifest(m, path)
        data = json.loads(path.read_text())
        data["bm25_k1"] = 1  # int instead of float
        path.write_text(json.dumps(data))
        recovered = read_manifest(path)
        assert recovered.bm25_k1 == 1.0

    def test_non_object_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text('["not", "an", "object"]')
        with pytest.raises(ValueError, match="must be a JSON object"):
            read_manifest(path)


class TestAtomicWrite:
    def test_write_creates_file(self, tmp_path: Path) -> None:
        m = _sample_manifest()
        path = tmp_path / "new_manifest.json"
        assert not path.exists()
        write_manifest(m, path)
        assert path.exists()

    def test_write_overwrites_existing(self, tmp_path: Path) -> None:
        m1 = _sample_manifest()
        m2 = Manifest(
            corpus_source="other_source",
            corpus_commit_sha="xyz789",
            tokenizer_version=2,
            embed_endpoint="https://other.api/v1",
            embed_model="other-model",
            embed_dim=768,
            embed_normalized=False,
            bm25_lib="bm25s",
            bm25_lib_version="0.3.0",
            bm25_k1=1.5,
            bm25_b=0.8,
            vec_schema_version=2,
            nonverse_chunk_cap=256,
            nonverse_chunk_floor=32,
        )
        path = tmp_path / "manifest.json"
        write_manifest(m1, path)
        write_manifest(m2, path)
        recovered = read_manifest(path)
        assert recovered == m2
