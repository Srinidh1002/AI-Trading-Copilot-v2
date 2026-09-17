"""Bounded Windows-safe atomic replacement for Task 9 durable files."""
from __future__ import annotations

import os
import time
from pathlib import Path


def replace_task9_atomic_file(
    source: str | Path,
    destination: str | Path,
    *,
    max_attempts: int = 5,
    base_delay_seconds: float = 0.05,
) -> None:
    """Atomically replace one Task 9 durable file with bounded PermissionError retry."""
    source_path = Path(source)
    destination_path = Path(destination)

    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts")

    if (
        type(base_delay_seconds) not in {int, float}
        or base_delay_seconds < 0
    ):
        raise ValueError("base_delay_seconds")

    for attempt in range(max_attempts):
        try:
            os.replace(source_path, destination_path)
            return
        except PermissionError:
            if attempt == max_attempts - 1:
                raise

            time.sleep(
                float(base_delay_seconds) * (attempt + 1)
            )

    raise RuntimeError("unreachable Task 9 atomic replace state")
