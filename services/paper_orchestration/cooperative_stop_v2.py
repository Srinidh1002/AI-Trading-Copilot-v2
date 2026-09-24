"""Cooperative stop protocol for PAPER workers.

The supervisor writes a stop-request file and waits for the worker's ACK.
The worker polls the request on every loop iteration. ACK status is one of:

  FLAT_SAFE_TO_EXIT        — worker is flat; supervisor may allow exit
  POSITION_MANAGEMENT_ACTIVE — worker holds an open PAPER position and
                              continues managing to terminal
  TERMINAL_RECONCILED      — position terminal and reconciled; safe to exit
  STATE_HOLD               — worker cannot proceed; supervisor must stop it

ACK payload contains only non-sensitive fields: market, pid, status,
timestamp, reason, has_active_position boolean, and (optionally) a
trade_id string. No tokens, no secrets.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

STATUS_FLAT_SAFE_TO_EXIT = "FLAT_SAFE_TO_EXIT"
STATUS_POSITION_MANAGEMENT_ACTIVE = "POSITION_MANAGEMENT_ACTIVE"
STATUS_TERMINAL_RECONCILED = "TERMINAL_RECONCILED"
STATUS_STATE_HOLD = "STATE_HOLD"

_ALLOWED_STATUSES = frozenset(
    {
        STATUS_FLAT_SAFE_TO_EXIT,
        STATUS_POSITION_MANAGEMENT_ACTIVE,
        STATUS_TERMINAL_RECONCILED,
        STATUS_STATE_HOLD,
    }
)


def _request_path():
    raw = os.environ.get("PAPER_STOP_REQUEST_FILE")
    return Path(raw) if raw else None


def _ack_path():
    raw = os.environ.get("PAPER_STOP_ACK_FILE")
    return Path(raw) if raw else None


def _market_name():
    return str(os.environ.get("PAPER_MARKET_NAME") or "")


def stop_requested():
    p = _request_path()
    if p is None:
        return False
    try:
        return p.exists()
    except OSError:
        return False


def acknowledge(
    *,
    reason="STOP_NEW_ENTRIES",
    status=STATUS_FLAT_SAFE_TO_EXIT,
    has_active_position=False,
    trade_id=None,
    extra=None,
):
    """Write an ACK file. Idempotent overwrite.

    Never writes tokens or secrets. Never writes an unknown status.
    """
    p = _ack_path()
    if p is None:
        return
    if status not in _ALLOWED_STATUSES:
        status = STATUS_STATE_HOLD
    payload = {
        "acked_at_utc": datetime.now(UTC).isoformat(),
        "pid": os.getpid(),
        "market": _market_name(),
        "status": status,
        "reason": str(reason),
        "has_active_position": bool(has_active_position),
    }
    if trade_id:
        payload["trade_id"] = str(trade_id)
    if extra and isinstance(extra, dict):
        for k, v in extra.items():
            # Never leak token-like fields, ever.
            lk = str(k).lower()
            if "token" in lk or "secret" in lk or "pin" in lk or "pass" in lk:
                continue
            payload[k] = v
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def read_ack():
    """Read the current ACK payload. Returns dict or None. Never raises."""
    p = _ack_path()
    if p is None:
        return None
    try:
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
