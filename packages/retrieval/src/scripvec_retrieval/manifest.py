"""Index manifest dataclass and persistence."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .hashing import blake2b_128_hex, canonical_json

_MANIFEST_FIELDS = frozenset({
    "corpus_source",
    "corpus_commit_sha",
    "tokenizer_version",
    "embed_endpoint",
    "embed_model",
    "embed_dim",
    "embed_normalized",
    "bm25_lib",
    "bm25_lib_version",
    "bm25_k1",
    "bm25_b",
    "vec_schema_version",
    "nonverse_chunk_cap",
    "nonverse_chunk_floor",
})


@dataclass(frozen=True)
class Manifest:
    corpus_source: str
    corpus_commit_sha: str
    tokenizer_version: int
    embed_endpoint: str
    embed_model: str
    embed_dim: int
    embed_normalized: bool
    bm25_lib: str
    bm25_lib_version: str
    bm25_k1: float
    bm25_b: float
    vec_schema_version: int
    nonverse_chunk_cap: int
    nonverse_chunk_floor: int


def config_hash(m: Manifest) -> str:
    """Return BLAKE2b-128 hex digest of the manifest's canonical JSON."""
    return blake2b_128_hex(canonical_json(asdict(m)))


def write_manifest(m: Manifest, path: Path | str) -> None:
    """Atomically write manifest to path (write temp then replace)."""
    path = Path(path)
    data = json.dumps(asdict(m), indent=2, sort_keys=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".manifest_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_manifest(path: Path | str) -> Manifest:
    """Read manifest from path. Raises on missing/extra fields or type mismatch."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data: Any = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a JSON object, got {type(data).__name__}")

    keys = set(data.keys())
    missing = _MANIFEST_FIELDS - keys
    if missing:
        raise ValueError(f"Missing required manifest fields: {sorted(missing)}")

    extra = keys - _MANIFEST_FIELDS
    if extra:
        raise ValueError(f"Unknown manifest fields: {sorted(extra)}")

    try:
        return Manifest(
            corpus_source=_str(data, "corpus_source"),
            corpus_commit_sha=_str(data, "corpus_commit_sha"),
            tokenizer_version=_int(data, "tokenizer_version"),
            embed_endpoint=_str(data, "embed_endpoint"),
            embed_model=_str(data, "embed_model"),
            embed_dim=_int(data, "embed_dim"),
            embed_normalized=_bool(data, "embed_normalized"),
            bm25_lib=_str(data, "bm25_lib"),
            bm25_lib_version=_str(data, "bm25_lib_version"),
            bm25_k1=_float(data, "bm25_k1"),
            bm25_b=_float(data, "bm25_b"),
            vec_schema_version=_int(data, "vec_schema_version"),
            nonverse_chunk_cap=_int(data, "nonverse_chunk_cap"),
            nonverse_chunk_floor=_int(data, "nonverse_chunk_floor"),
        )
    except (TypeError, ValueError) as e:
        raise ValueError(f"Manifest type error: {e}") from e


def _str(d: dict[str, Any], key: str) -> str:
    v = d[key]
    if not isinstance(v, str):
        raise ValueError(f"Field '{key}' must be str, got {type(v).__name__}")
    return v


def _int(d: dict[str, Any], key: str) -> int:
    v = d[key]
    if not isinstance(v, int) or isinstance(v, bool):
        raise ValueError(f"Field '{key}' must be int, got {type(v).__name__}")
    return v


def _float(d: dict[str, Any], key: str) -> float:
    v = d[key]
    if isinstance(v, bool):
        raise ValueError(f"Field '{key}' must be float, got bool")
    if not isinstance(v, (int, float)):
        raise ValueError(f"Field '{key}' must be float, got {type(v).__name__}")
    return float(v)


def _bool(d: dict[str, Any], key: str) -> bool:
    v = d[key]
    if not isinstance(v, bool):
        raise ValueError(f"Field '{key}' must be bool, got {type(v).__name__}")
    return v
