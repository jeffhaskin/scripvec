"""Data directory layout helpers for scripvec retrieval."""

from __future__ import annotations

import os
import re
from pathlib import Path

_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def data_dir() -> Path:
    """Return the data directory, honoring SCRIPVEC_DATA_DIR env var.

    Returns:
        Path to data directory (default ./data/).
    """
    return Path(os.environ.get("SCRIPVEC_DATA_DIR", "./data/"))


def raw_dir() -> Path:
    """Return path to raw corpus data directory."""
    return data_dir() / "raw"


def eval_dir() -> Path:
    """Return path to evaluation data directory."""
    return data_dir() / "eval"


def logs_dir() -> Path:
    """Return path to logs directory."""
    return data_dir() / "logs"


def indexes_dir() -> Path:
    """Return path to indexes directory."""
    return data_dir() / "indexes"


def index_path(hash_hex: str) -> Path:
    """Return path to a specific index by its hash.

    Args:
        hash_hex: 32-character lowercase hex hash.

    Returns:
        Path to the index directory.

    Raises:
        ValueError: If hash_hex is not a valid 32-char hex string.
    """
    if not _HASH_PATTERN.match(hash_hex):
        raise ValueError(
            f"Invalid index hash: {hash_hex!r}. "
            f"Expected 32 lowercase hex characters."
        )
    return indexes_dir() / hash_hex


def latest_symlink() -> Path:
    """Return path to the 'latest' symlink in indexes directory."""
    return indexes_dir() / "latest"


def resolve_latest() -> str:
    """Resolve the 'latest' symlink to get the current index hash.

    Returns:
        The 32-character hex hash of the latest index.

    Raises:
        FileNotFoundError: If the 'latest' symlink does not exist.
        RuntimeError: If the symlink target is not a valid hash.
    """
    symlink = latest_symlink()
    if not symlink.exists():
        raise FileNotFoundError(
            f"No 'latest' symlink found at {symlink}. "
            f"Run 'scripvec index build' first."
        )

    target = symlink.resolve()
    hash_hex = target.name

    if not _HASH_PATTERN.match(hash_hex):
        raise RuntimeError(
            f"'latest' symlink points to invalid hash: {hash_hex!r}. "
            f"Expected 32 lowercase hex characters."
        )

    return hash_hex


def set_latest(hash_hex: str) -> None:
    """Atomically update the 'latest' symlink to point to a new index.

    Args:
        hash_hex: 32-character lowercase hex hash of the index.

    Raises:
        ValueError: If hash_hex is not a valid 32-char hex string.
        FileNotFoundError: If the target index directory does not exist.
    """
    target = index_path(hash_hex)

    if not target.is_dir():
        raise FileNotFoundError(
            f"Cannot set latest: index directory not found at {target}"
        )

    symlink = latest_symlink()
    symlink.parent.mkdir(parents=True, exist_ok=True)

    temp_link = symlink.with_suffix(".tmp")
    temp_link.unlink(missing_ok=True)
    temp_link.symlink_to(hash_hex)
    os.replace(temp_link, symlink)
