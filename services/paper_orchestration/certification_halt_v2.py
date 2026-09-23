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
    """Read countable trade count from either schema.

    INDEX: has certification_counter (int).
    MCX:   has _counted_trade_ids (list); no explicit counter key.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return 0

    v = data.get("certification_counter")
    if v is not None:
        return int(v)

    ids = data.get("_counted_trade_ids")
    if isinstance(ids, list):
        return len(ids)

    for k in ("counted_trade_ids", "countable_trades"):
        v = data.get(k)
        if isinstance(v, list):
            return len(v)
        if isinstance(v, int):
            return v

    return 0


def snapshot(markets=None):
    markets = markets or _ALL_MARKETS
    return {
        m: _counter(os.path.join(_STATE_DIR, f"{m}_experimental.json"))
        for m in markets
    }


def all_complete(markets=None) -> bool:
    return all(v >= _TARGET for v in snapshot(markets).values())

_SPEC_NAME_TO_FILE_KEY = {
    "NIFTY": "nifty",
    "SENSEX": "sensex",
    "CRUDEOILM": "mcx_crudeoilm",
    "GOLDM": "mcx_goldm",
    "NATGASMINI": "mcx_natgasmini",
}


def market_counter(spec_name):
    """Countable trades for one market, keyed by supervisor spec name."""
    key = _SPEC_NAME_TO_FILE_KEY.get(spec_name.upper(), spec_name.lower())
    return _counter(os.path.join(_STATE_DIR, f"{key}_experimental.json"))


def market_complete(spec_name):
    """True when this single market has reached the 100-trade target."""
    return market_counter(spec_name) >= _TARGET
