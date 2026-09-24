"""Certification authority — read-only countable-trade ledger for every market.

Fail-closed. Any state file that cannot be reconciled to a coherent
countable-trade record reports HOLD with an explicit reason. It never
silently maps unknown state to zero.

Public API:
  market_state(spec_name) -> MarketState
  snapshot(markets=None) -> dict[str, MarketState]
  market_counter(spec_name) -> int (raises CertificationStateAuthorityError on HOLD)
  market_complete(spec_name) -> bool (False on HOLD)
  all_complete(markets=None) -> bool
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

_STATE_DIR = os.path.join("data", "paper_trades")
_ALL_MARKETS = ("nifty", "sensex", "mcx_crudeoilm", "mcx_goldm", "mcx_natgasmini")
_TARGET = 100

_SPEC_NAME_TO_FILE_KEY = {
    "NIFTY": "nifty",
    "SENSEX": "sensex",
    "CRUDEOILM": "mcx_crudeoilm",
    "GOLDM": "mcx_goldm",
    "NATGASMINI": "mcx_natgasmini",
}

_STATUS_VALID = "VALID_COUNTER"
_STATUS_COMPLETE = "COMPLETE"
_STATUS_HOLD = "HOLD"


class CertificationStateAuthorityError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarketState:
    market: str
    status: str
    counter: int | None
    reason: str | None = None


def _state_path(key: str) -> str:
    return os.path.join(_STATE_DIR, f"{key}_experimental.json")


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise CertificationStateAuthorityError("CERTIFICATION_STATE_MISSING") from exc
    except (OSError, ValueError) as exc:
        raise CertificationStateAuthorityError("CERTIFICATION_STATE_UNREADABLE") from exc
    if not isinstance(data, dict):
        raise CertificationStateAuthorityError("CERTIFICATION_STATE_SCHEMA_INVALID")
    return data


def _count_index_schema(data: dict) -> int:
    v = data.get("certification_counter")
    if not isinstance(v, int) or v < 0:
        raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_INVALID")
    ids = data.get("counted_trade_ids")
    if not isinstance(ids, list):
        raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_INCOHERENT")
    if len(ids) != v or len(set(map(str, ids))) != len(ids):
        raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_INCOHERENT")
    wins = data.get("certification_wins")
    losses = data.get("certification_losses")
    if isinstance(wins, int) and isinstance(losses, int):
        if wins < 0 or losses < 0 or wins + losses != v:
            raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_INCOHERENT")
    return v


def _count_mcx_schema(data: dict) -> int:
    ids = data.get("_counted_trade_ids")
    wins = int(data.get("t1_hit_wins", 0) or 0)
    losses = int(data.get("sl_losses", 0) or 0)
    if isinstance(ids, list):
        if len(ids) != len(set(map(str, ids))):
            raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_INCOHERENT")
        if wins < 0 or losses < 0 or len(ids) != wins + losses:
            raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_INCOHERENT")
        return len(ids)
    # Pre-migration MCX schema. Accept only when every counter is zero
    # and no completed trades exist. Any nonzero value is unreconcilable.
    total = int(data.get("total_trades", 0) or 0)
    completed = data.get("completed_trades")
    if wins == 0 and losses == 0 and total == 0:
        if completed is None or (isinstance(completed, list) and len(completed) == 0):
            return 0
    raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_MISSING")


def _counter(key: str) -> int:
    data = _read_json(_state_path(key))
    if "certification_counter" in data:
        return _count_index_schema(data)
    if "_counted_trade_ids" in data or "t1_hit_wins" in data or "sl_losses" in data:
        return _count_mcx_schema(data)
    raise CertificationStateAuthorityError("CERTIFICATION_COUNTER_MISSING")


def _file_key(spec_name: str) -> str:
    return _SPEC_NAME_TO_FILE_KEY.get(spec_name.upper(), spec_name.lower())


def market_state(spec_name: str) -> MarketState:
    key = _file_key(spec_name)
    try:
        c = _counter(key)
    except CertificationStateAuthorityError as exc:
        return MarketState(spec_name, _STATUS_HOLD, None, str(exc))
    if c >= _TARGET:
        return MarketState(spec_name, _STATUS_COMPLETE, c)
    return MarketState(spec_name, _STATUS_VALID, c)


def snapshot(markets=None) -> dict:
    return {m: market_state(m) for m in (markets or _ALL_MARKETS)}


def market_counter(spec_name: str) -> int:
    st = market_state(spec_name)
    if st.status == _STATUS_HOLD:
        raise CertificationStateAuthorityError(st.reason or "HOLD")
    return st.counter


def market_complete(spec_name: str) -> bool:
    return market_state(spec_name).status == _STATUS_COMPLETE


def all_complete(markets=None) -> bool:
    return all(st.status == _STATUS_COMPLETE for st in snapshot(markets).values())
