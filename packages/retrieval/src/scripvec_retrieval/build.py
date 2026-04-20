"""Index builder with corpus-drift guard per CR-002."""

from __future__ import annotations

from pathlib import Path

import bm25s

from scripvec_corpus_ingest.bcbooks import corpus_commit_sha, iter_verses
from scripvec_corpus_ingest.chunker import _NONVERSE_CHUNK_CAP, _NONVERSE_CHUNK_FLOOR
from scripvec_corpus_ingest.verse import VerseRecord

from .bm25 import build_bm25
from .config import load_embed_config
from .embed import embed_verse_chunk
from .manifest import Manifest, config_hash, read_manifest, write_manifest
from .paths import data_dir, index_path, indexes_dir, set_latest
from .store import insert_batch, open_store
from .tokenizer import TOKENIZER_VERSION


def _assemble_manifest(commit_sha: str) -> Manifest:
    """Assemble manifest from current config and corpus state."""
    cfg = load_embed_config()

    return Manifest(
        corpus_source="bcbooks",
        corpus_commit_sha=commit_sha,
        tokenizer_version=TOKENIZER_VERSION,
        embed_endpoint=cfg.base_url,
        embed_model=cfg.model,
        embed_dim=cfg.dim,
        embed_normalized=True,
        bm25_lib="bm25s",
        bm25_lib_version=bm25s.__version__,
        bm25_k1=1.5,
        bm25_b=0.75,
        vec_schema_version=1,
        nonverse_chunk_cap=_NONVERSE_CHUNK_CAP,
        nonverse_chunk_floor=_NONVERSE_CHUNK_FLOOR,
    )


def _drift_check_corpus(
    stored_sha: str | None,
    observed_sha: str,
    rebuild_corpus: bool,
) -> None:
    """Check for corpus drift between stored and observed commit SHA.

    Args:
        stored_sha: SHA from existing manifest, or None for from-scratch.
        observed_sha: Current corpus commit SHA.
        rebuild_corpus: If True, allow drift and rebuild.

    Raises:
        RuntimeError: If commits differ and rebuild_corpus is False.
    """
    if stored_sha is None:
        return

    if stored_sha == observed_sha:
        return

    if rebuild_corpus:
        return

    raise RuntimeError(
        f"Corpus drift detected: stored={stored_sha}, observed={observed_sha}. "
        f"Use rebuild_corpus=True to force rebuild."
    )


def build_index(
    *,
    from_scratch: bool = True,
    rebuild_corpus: bool = False,
) -> str:
    """Build the search index from corpus.

    Full sequence per CR-002:
    1. Corpus-drift check
    2. Load verses (non-verse chunks out of MVP scope)
    3. Assemble manifest and compute config_hash
    4. Serial embed with ADR-015 telemetry
    5. Transactional insert into sqlite-vec store
    6. Build BM25 index
    7. Write manifest
    8. Set latest symlink (atomic publish)

    Args:
        from_scratch: If True, build fresh. If False, raises NotImplementedError.
        rebuild_corpus: If True, allow corpus drift for incremental rebuilds.

    Returns:
        The config hash of the built index.

    Raises:
        NotImplementedError: If from_scratch is False (incremental out of MVP).
        RuntimeError: On corpus drift, embed failures, or other errors.
    """
    if not from_scratch:
        raise NotImplementedError("Incremental index building is out of MVP scope")

    data = data_dir()
    observed_sha = corpus_commit_sha(data)

    stored_sha: str | None = None
    if not from_scratch:
        try:
            latest_dir = indexes_dir() / "latest"
            if latest_dir.exists():
                manifest = read_manifest(latest_dir / "manifest.json")
                stored_sha = manifest.corpus_commit_sha
        except FileNotFoundError:
            pass

    _drift_check_corpus(stored_sha, observed_sha, rebuild_corpus)

    manifest = _assemble_manifest(observed_sha)
    hash_hex = config_hash(manifest)

    idx_dir = index_path(hash_hex)
    idx_dir.mkdir(parents=True, exist_ok=True)

    store_path = idx_dir / "corpus.sqlite"
    store = open_store(store_path, create=True)

    verses: list[VerseRecord] = []
    batch: list[tuple[VerseRecord, list[float]]] = []
    batch_size = 100

    try:
        for verse in iter_verses(data):
            verses.append(verse)
            embedding = embed_verse_chunk(verse.text)
            batch.append((verse, embedding))

            if len(batch) >= batch_size:
                insert_batch(store, batch)
                batch = []

        if batch:
            insert_batch(store, batch)

        build_bm25(verses, idx_dir)

        write_manifest(manifest, idx_dir / "manifest.json")

        set_latest(hash_hex)

    finally:
        store.conn.close()

    return hash_hex
