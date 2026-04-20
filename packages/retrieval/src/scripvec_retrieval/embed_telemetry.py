"""Embed call latency telemetry per ADR-015."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .paths import logs_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbedConfig:
    """Configuration tuple for telemetry scoping."""

    endpoint: str
    model: str
    dim: int
    normalize: bool

    def config_hash(self) -> str:
        """Return a stable hash of this config for filename use."""
        data = f"{self.endpoint}|{self.model}|{self.dim}|{self.normalize}"
        return hashlib.md5(data.encode()).hexdigest()[:16]


@dataclass
class RunningAverage:
    """Running average state."""

    config_hash: str
    count: int
    total_ms: float
    average_ms: float


@dataclass(frozen=True)
class TimingRecord:
    """Single timing record for the append-only log."""

    timestamp: str
    config_hash: str
    latency_ms: float


def _timing_log_path() -> Path:
    """Return path to the timing log file."""
    return logs_dir() / "embed_timing.jsonl"


def _average_state_path(config_hash: str) -> Path:
    """Return path to the running average state file for a config."""
    return logs_dir() / f"embed_avg_{config_hash}.json"


def _write_timing_record(record: TimingRecord) -> None:
    """Append a timing record to the log. Warns but does not raise on failure."""
    try:
        log_path = _timing_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(record), separators=(",", ":")) + "\n"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        logger.warning("Failed to write embed timing record: %s", e)


def _save_average_state(state: RunningAverage) -> None:
    """Save running average state. Warns but does not raise on failure."""
    try:
        path = _average_state_path(state.config_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(state), f)
    except OSError as e:
        logger.warning("Failed to save embed average state: %s", e)


def _load_average_state(config_hash: str) -> RunningAverage | None:
    """Load running average state from file, or None if missing."""
    path = _average_state_path(config_hash)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return RunningAverage(**data)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise RuntimeError(f"Corrupt embed average state file {path}: {e}") from e


def _derive_average_from_log(config_hash: str) -> RunningAverage:
    """Re-derive running average from the append-only log."""
    log_path = _timing_log_path()
    count = 0
    total_ms = 0.0

    if log_path.exists():
        try:
            with log_path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("config_hash") == config_hash:
                            count += 1
                            total_ms += record["latency_ms"]
                    except (json.JSONDecodeError, KeyError) as e:
                        raise RuntimeError(
                            f"Corrupt embed timing log at line {line_num}: {e}"
                        ) from e
        except OSError as e:
            raise RuntimeError(f"Failed to read embed timing log: {e}") from e

    average_ms = total_ms / count if count > 0 else 0.0
    return RunningAverage(
        config_hash=config_hash,
        count=count,
        total_ms=total_ms,
        average_ms=average_ms,
    )


class EmbedTelemetry:
    """Telemetry tracker for embed calls."""

    def __init__(self, config: EmbedConfig) -> None:
        """Initialize telemetry for a specific config.

        Raises:
            RuntimeError: If state files are corrupt.
        """
        self._config = config
        self._config_hash = config.config_hash()

        state = _load_average_state(self._config_hash)
        if state is None:
            state = _derive_average_from_log(self._config_hash)
            _save_average_state(state)

        self._state = state

    def record(self, latency_ms: float) -> None:
        """Record a single embed call latency.

        Args:
            latency_ms: Time from request initiation to normalized vector returned.
        """
        record = TimingRecord(
            timestamp=datetime.now(UTC).isoformat(),
            config_hash=self._config_hash,
            latency_ms=latency_ms,
        )
        _write_timing_record(record)

        self._state = RunningAverage(
            config_hash=self._config_hash,
            count=self._state.count + 1,
            total_ms=self._state.total_ms + latency_ms,
            average_ms=(self._state.total_ms + latency_ms) / (self._state.count + 1),
        )
        _save_average_state(self._state)

    @property
    def average_ms(self) -> float:
        """Return the current running average latency in milliseconds."""
        return self._state.average_ms

    @property
    def count(self) -> int:
        """Return the number of recorded calls."""
        return self._state.count
