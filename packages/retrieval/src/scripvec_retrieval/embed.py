"""Sanctioned embed client per ADRs 005, 006, 001, 015."""

from __future__ import annotations

import math
import time
from typing import Any

import httpx

from .config import EmbedConfig, load_embed_config
from .embed_telemetry import EmbedConfig as TelemetryConfig
from .embed_telemetry import EmbedTelemetry

_MAX_TOKENS = 8000


def _estimate_token_count(text: str) -> int:
    """Conservative upper bound on token count: char/3 + word_count."""
    char_estimate = len(text) // 3
    word_count = len(text.split())
    return char_estimate + word_count


def _l2_normalize(vec: list[float]) -> list[float]:
    """L2-normalize a vector. Raises RuntimeError on zero norm."""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        raise RuntimeError("Cannot L2-normalize zero vector")
    return [x / norm for x in vec]


def _post_embedding(cfg: EmbedConfig, text: str) -> list[float]:
    """POST to embedding endpoint and parse response. Raises on HTTP/parsing errors."""
    url = f"{cfg.base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": cfg.model, "input": text}

    response = httpx.post(url, json=payload, headers=headers, timeout=60.0)

    if response.status_code != 200:
        raise RuntimeError(
            f"Embedding request failed with status {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
        embedding = data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Malformed embedding response: {e}") from e

    if not isinstance(embedding, list):
        raise RuntimeError(f"Embedding is not a list: {type(embedding)}")

    return embedding


def embed(text: str, *, _verse_chunk: bool = False) -> list[float]:
    """Embed text and return L2-normalized vector.

    Synchronous, serial, dim-checked per ADR-005/006. Single sanctioned entry point.

    Args:
        text: Text to embed.
        _verse_chunk: If True, records latency to telemetry (ADR-015).
            Use for verse-chunk embed calls during ingest, not for queries.

    Returns:
        L2-normalized embedding vector of dimension matching config.

    Raises:
        RuntimeError: On >8K token input, non-2xx HTTP, dim mismatch, malformed response.
    """
    token_estimate = _estimate_token_count(text)
    if token_estimate > _MAX_TOKENS:
        raise RuntimeError(
            f"Input exceeds {_MAX_TOKENS} token limit (estimated {token_estimate} tokens)"
        )

    cfg = load_embed_config()

    start_time = time.perf_counter()
    raw_vec = _post_embedding(cfg, text)
    latency_ms = (time.perf_counter() - start_time) * 1000

    if len(raw_vec) != cfg.dim:
        raise RuntimeError(
            f"Embedding dimension mismatch: expected {cfg.dim}, got {len(raw_vec)}"
        )

    normalized = _l2_normalize(raw_vec)

    if _verse_chunk:
        telemetry_cfg = TelemetryConfig(
            endpoint=cfg.base_url,
            model=cfg.model,
            dim=cfg.dim,
            normalize=True,
        )
        telemetry = EmbedTelemetry(telemetry_cfg)
        telemetry.record(latency_ms)

    return normalized


def embed_verse_chunk(text: str) -> list[float]:
    """Embed a verse chunk with telemetry recording (ADR-015).

    Convenience wrapper for ingest code that embeds verse-chunks and wants
    latency tracking. Equivalent to `embed(text, _verse_chunk=True)`.
    """
    return embed(text, _verse_chunk=True)
