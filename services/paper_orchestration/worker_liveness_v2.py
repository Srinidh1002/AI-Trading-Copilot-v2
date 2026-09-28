"""Worker liveness classifier — Phase 6 of F15-R1.

PAPER-only. Read-only. Pure functions.

Reads a worker heartbeat JSON written by worker_heartbeat_v2.beat()
and classifies liveness relative to wall clock.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

# Conservative default. Live NATGAS chain call observed at ~43 s.
# Worst-case legitimate gap between two heartbeat writes is one full
# cycle (60 s) plus a slow CHAIN+MTF+EXTERNAL+VWAP sequence. 300 s
# gives roughly 2x headroom over the worst plausible healthy case.
HEARTBEAT_MAX_AGE_SECONDS = 300.0

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DIR = _REPO_ROOT / "logs" / "supervisor" / "heartbeats"


def heartbeat_dir() -> Path:
    override = os.environ.get("PAPER_HEARTBEAT_DIR")
    if override:
        return Path(override)
    return _DEFAULT_DIR


def read_heartbeat(market: str):
    """Return the parsed heartbeat dict, or None if absent/unparsable."""
    path = heartbeat_dir() / (market.upper() + ".json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def heartbeat_age_seconds(hb, now):
    """Seconds between hb["timestamp"] and now, or None if unusable."""
    if not isinstance(hb, dict):
        return None
    ts = hb.get("timestamp")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return (now - dt).total_seconds()


def classify(market, now, *, max_age_seconds=HEARTBEAT_MAX_AGE_SECONDS):
    """Return (classification, heartbeat_dict, age_seconds_or_none).

    classification is one of:
      "NO_HEARTBEAT"     no file, unparsable, or missing/invalid timestamp
      "HEARTBEAT_OK"     age <= max_age_seconds
      "HEARTBEAT_STALE"  age  > max_age_seconds
    """
    hb = read_heartbeat(market)
    if hb is None:
        return ("NO_HEARTBEAT", {}, None)
    age = heartbeat_age_seconds(hb, now)
    if age is None:
        return ("NO_HEARTBEAT", hb, None)
    if age > max_age_seconds:
        return ("HEARTBEAT_STALE", hb, age)
    return ("HEARTBEAT_OK", hb, age)
