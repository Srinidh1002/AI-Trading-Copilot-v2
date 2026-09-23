"""Detects when every enabled market has reached 100 countable trades.

Pure read-only. The supervisor consults this at every tick.
"""
from __future__ import annotations

import json
import os

_STATE_DIR = os.path.join("data", "paper_trades")
_ALL_MARKETS = ("nifty", "sensex", "mcx_crudeoilm", "mcx_goldm", "mcx_natgasmini")
_TARGET = 100


def _counter(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return 0
    for key in ("certification_counter", "countable_trades", "trades"):
        v = data.get(key)
        if v is not None:
            return int(v)
    return 0


def snapshot(markets=None):
    markets = markets or _ALL_MARKETS
    return {
        m: _counter(os.path.join(_STATE_DIR, f"{m}_experimental.json"))
        for m in markets
    }


def all_complete(markets=None) -> bool:
    return all(v >= _TARGET for v in snapshot(markets).values())
