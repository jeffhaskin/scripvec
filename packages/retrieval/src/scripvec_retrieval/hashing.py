"""Canonical JSON serialization and BLAKE2b hashing for index manifests."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """Serialize object to canonical JSON bytes (sorted keys, no whitespace, UTF-8)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def blake2b_128_hex(payload: bytes) -> str:
    """Return 32-char lowercase hex digest of BLAKE2b-128."""
    return hashlib.blake2b(payload, digest_size=16).hexdigest()
