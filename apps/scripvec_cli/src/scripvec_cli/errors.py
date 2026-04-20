"""Exit codes and structured error output for scripvec CLI."""

from __future__ import annotations

import json
import sys
from enum import IntEnum
from typing import NoReturn


class ExitCode(IntEnum):
    """CLI exit codes per ADR-007."""

    SUCCESS = 0
    USER_ERROR = 1
    NOT_FOUND = 2
    UPSTREAM_ERROR = 3


def emit_error(
    code: str,
    message: str,
    details: str | None = None,
    exit_code: ExitCode = ExitCode.USER_ERROR,
) -> NoReturn:
    """Write structured error JSON to stderr and exit."""
    error_obj: dict[str, str | None] = {
        "code": code,
        "message": message,
        "details": details,
    }
    output = {"error": error_obj}
    sys.stderr.write(json.dumps(output) + "\n")
    sys.exit(exit_code)
