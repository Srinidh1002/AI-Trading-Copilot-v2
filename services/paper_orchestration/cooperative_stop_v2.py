"""Cooperative stop protocol for PAPER workers.

The supervisor writes a stop-request file and waits for the worker's ACK.
The worker polls the request on every loop iteration:

  * stop requested and flat -> save state, write ACK, exit cleanly
  * stop requested and open -> stop taking new entries, continue managing
    the position to terminal, then save, ACK, exit cleanly

Files are named via environment variables set by the supervisor:
  PAPER_STOP_REQUEST_FILE  (path to poll)
  PAPER_STOP_ACK_FILE      (path to write on exit)

If either variable is unset, all functions are no-ops.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _request_path() -> Path | None:
    raw = os.environ.get("PAPER_STOP_REQUEST_FILE")
    return Path(raw) if raw else None


def _ack_path() -> Path | None:
    raw = os.environ.get("PAPER_STOP_ACK_FILE")
    return Path(raw) if raw else None


def stop_requested() -> bool:
    p = _request_path()
    if p is None:
        return False
    try:
        return p.exists()
    except OSError:
        return False


def acknowledge(*, reason: str = "STOP_NEW_ENTRIES", extra: dict | None = None) -> None:
    """Write an ACK file. Does not modify the request. Idempotent overwrite."""
    p = _ack_path()
    if p is None:
        return
    payload = {
        "acked_at_utc": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "reason": reason,
    }
    if extra:
        for k, v in extra.items():
            payload[k] = v
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass
