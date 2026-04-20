"""SQLite-vec store for verse embeddings."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import sqlite_vec

from scripvec_corpus_ingest.verse import VerseRecord
from scripvec_retrieval.config import load_embed_config


@dataclass
class StoreConn:
    """SQLite connection with sqlite-vec extension loaded."""

    conn: sqlite3.Connection
    dim: int


@dataclass(frozen=True)
class DenseHit:
    """Dense retrieval hit with similarity score."""

    verse_id: str
    rowid: int
    cosine: float
    record: VerseRecord


def open_store(path: str | Path, *, create: bool = False) -> StoreConn:
    """Open or create the corpus store.

    Args:
        path: Path to corpus.sqlite file.
        create: If True, create tables if they don't exist.

    Returns:
        StoreConn with loaded sqlite-vec extension.

    Raises:
        FileNotFoundError: If create=False and file doesn't exist.
        RuntimeError: If extension load fails or dim drift detected.
    """
    path = Path(path)
    config = load_embed_config()
    dim = config.dim

    if not create and not path.exists():
        raise FileNotFoundError(f"Store not found: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:
        conn.close()
        raise RuntimeError(f"Failed to load sqlite-vec extension: {e}") from e

    if create:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verses (
                rowid INTEGER PRIMARY KEY,
                verse_id TEXT UNIQUE NOT NULL,
                ref_canonical TEXT NOT NULL,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                text TEXT NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_verses USING vec0(
                rowid INTEGER PRIMARY KEY,
                embedding float[{dim}]
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS store_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT OR REPLACE INTO store_meta (key, value) VALUES (?, ?)",
            ("dim", str(dim)),
        )
        conn.commit()
    else:
        row = conn.execute(
            "SELECT value FROM store_meta WHERE key = ?", ("dim",)
        ).fetchone()
        if row:
            stored_dim = int(row["value"])
            if stored_dim != dim:
                conn.close()
                raise RuntimeError(
                    f"Dim drift: store has dim={stored_dim}, config has dim={dim}"
                )

    return StoreConn(conn=conn, dim=dim)


def insert_batch(
    store: StoreConn,
    rows: Sequence[tuple[VerseRecord, list[float]]],
) -> None:
    """Insert verses and embeddings in a single transaction.

    Args:
        store: Open store connection.
        rows: Sequence of (VerseRecord, embedding_vector) tuples.

    Raises:
        ValueError: If any embedding has wrong dimension.
    """
    conn = store.conn
    dim = store.dim

    with conn:
        for record, embedding in rows:
            if len(embedding) != dim:
                raise ValueError(
                    f"Dim mismatch for {record.verse_id}: "
                    f"got {len(embedding)}, expected {dim}"
                )

            cursor = conn.execute(
                """
                INSERT INTO verses (verse_id, ref_canonical, book, chapter, verse, text)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.verse_id,
                    record.ref_canonical,
                    record.book,
                    record.chapter,
                    record.verse,
                    record.text,
                ),
            )
            rowid = cursor.lastrowid

            conn.execute(
                "INSERT INTO vec_verses (rowid, embedding) VALUES (?, ?)",
                (rowid, sqlite_vec.serialize_float32(embedding)),
            )


def dense_topk(
    store: StoreConn,
    query_vec: list[float],
    k: int = 50,
) -> list[DenseHit]:
    """Find top-k verses by cosine similarity.

    Inner product over L2-normalized vectors equals cosine similarity.

    Args:
        store: Open store connection.
        query_vec: L2-normalized query embedding.
        k: Number of results to return.

    Returns:
        List of DenseHit sorted by descending similarity.
    """
    conn = store.conn

    rows = conn.execute(
        """
        SELECT
            v.rowid,
            v.verse_id,
            v.ref_canonical,
            v.book,
            v.chapter,
            v.verse,
            v.text,
            vec.distance
        FROM vec_verses vec
        JOIN verses v ON v.rowid = vec.rowid
        WHERE vec.embedding MATCH ?
            AND k = ?
        ORDER BY vec.distance ASC
        """,
        (sqlite_vec.serialize_float32(query_vec), k),
    ).fetchall()

    results: list[DenseHit] = []
    for row in rows:
        record = VerseRecord(
            verse_id=row["verse_id"],
            ref_canonical=row["ref_canonical"],
            book=row["book"],
            chapter=row["chapter"],
            verse=row["verse"],
            text=row["text"],
        )
        cosine = 1.0 - row["distance"]
        results.append(
            DenseHit(
                verse_id=row["verse_id"],
                rowid=row["rowid"],
                cosine=cosine,
                record=record,
            )
        )

    return results


def get_verse(store: StoreConn, verse_id: str) -> VerseRecord:
    """Fetch a single verse by ID.

    Args:
        store: Open store connection.
        verse_id: Unique verse identifier.

    Returns:
        VerseRecord for the verse.

    Raises:
        KeyError: If verse_id not found.
    """
    conn = store.conn

    row = conn.execute(
        """
        SELECT verse_id, ref_canonical, book, chapter, verse, text
        FROM verses
        WHERE verse_id = ?
        """,
        (verse_id,),
    ).fetchone()

    if row is None:
        raise KeyError(f"Verse not found: {verse_id}")

    return VerseRecord(
        verse_id=row["verse_id"],
        ref_canonical=row["ref_canonical"],
        book=row["book"],
        chapter=row["chapter"],
        verse=row["verse"],
        text=row["text"],
    )
