"""Pure read-only state authority checks for preflight and diagnostics.

This module NEVER mutates state. It reads each market state file and
returns a Verdict describing whether the file would pass the runtime
loader's authority gate. It does not perform orphan purge, does not write
to disk, and does not touch os.environ.

Runtime loaders (src/target_focused_bot.py::load_state and
src/mcx/mcx_paper_bot.py::load_state) remain the sole authority that can
accept or reject a state file for trading. This module mirrors their
schema rules so the morning preflight can fail closed BEFORE a worker is
spawned.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


INDEX_MARKETS = ("NIFTY", "SENSEX")
MCX_MARKETS = ("CRUDEOILM", "GOLDM", "NATGASMINI")

INDEX_STRATEGY_VERSION = "NS_DESIGN_B_BID_AUTH_V3"
INDEX_CERTIFICATION_EPOCH = "NS_CERT_20260916_V3"

_MARKET_TO_FILE_KEY = {
    "NIFTY": "nifty",
    "SENSEX": "sensex",
    "CRUDEOILM": "mcx_crudeoilm",
    "GOLDM": "mcx_goldm",
    "NATGASMINI": "mcx_natgasmini",
}


@dataclass(frozen=True)
class Verdict:
    market: str
    ok: bool
    reason: str
    note: str = ""


def _state_path(repo_root: Path, market: str) -> Path:
    key = _MARKET_TO_FILE_KEY.get(market.upper(), market.lower())
    return repo_root / "data" / "paper_trades" / f"{key}_experimental.json"


def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except OSError as exc:
        return ("__OSERROR__", exc)
    except ValueError as exc:
        return ("__JSONERROR__", exc)


def _validate_index(repo_root: Path, market: str) -> Verdict:
    p = _state_path(repo_root, market)
    data = _load_json(p)
    if data is None:
        return Verdict(market, False, "STATE_MISSING")
    if isinstance(data, tuple):
        tag = "STATE_UNREADABLE" if data[0] == "__OSERROR__" else "STATE_CORRUPT_JSON"
        return Verdict(market, False, tag)
    if not isinstance(data, dict):
        return Verdict(market, False, "STATE_SCHEMA_INVALID")

    if data.get("market") != market:
        return Verdict(market, False, "STATE_MARKET_MISMATCH",
                       f"file market={data.get('market')!r}")

    sv = data.get("strategy_version")
    ce = data.get("certification_epoch")
    if sv is None or ce is None:
        return Verdict(market, False, "STATE_EPOCH_MISSING",
                       "legacy state without epoch metadata cannot authorize a certified run")
    if sv != INDEX_STRATEGY_VERSION:
        return Verdict(market, False, "STATE_STRATEGY_VERSION_MISMATCH",
                       f"{sv!r} != {INDEX_STRATEGY_VERSION!r}")
    if ce != INDEX_CERTIFICATION_EPOCH:
        return Verdict(market, False, "STATE_EPOCH_MISMATCH",
                       f"{ce!r} != {INDEX_CERTIFICATION_EPOCH!r}")

    counter = data.get("certification_counter")
    ids = data.get("counted_trade_ids")
    if not isinstance(counter, int) or counter < 0:
        return Verdict(market, False, "STATE_COUNTER_INVALID")
    if not isinstance(ids, list):
        return Verdict(market, False, "STATE_COUNTED_IDS_INVALID")
    if len(ids) != len(set(ids)):
        return Verdict(market, False, "STATE_COUNTED_IDS_DUPLICATE")
    if len(ids) != counter:
        return Verdict(market, False, "STATE_COUNTER_INCOHERENT",
                       f"counter={counter} ids={len(ids)}")

    wins = data.get("certification_wins")
    losses = data.get("certification_losses")
    if isinstance(wins, int) and isinstance(losses, int):
        if wins < 0 or losses < 0 or wins + losses != counter:
            return Verdict(market, False, "STATE_WINS_LOSSES_INCOHERENT",
                           f"wins={wins} losses={losses} counter={counter}")

    active = data.get("active_trades")
    if active is None:
        active = []
    if not isinstance(active, list):
        return Verdict(market, False, "STATE_ACTIVE_LIST_INVALID")

    today = date.today()
    stale_active = 0
    for t in active:
        if not isinstance(t, dict):
            return Verdict(market, False, "STATE_MALFORMED_ACTIVE_TRADE")
        tid = t.get("trade_id")
        if not isinstance(tid, str) or not tid.strip():
            return Verdict(market, False, "STATE_MALFORMED_ACTIVE_TRADE",
                           "missing trade_id")
        et = t.get("entry_time")
        if not isinstance(et, str) or len(et) < 10:
            return Verdict(market, False, "STATE_MALFORMED_ACTIVE_ENTRY_TIME")
        try:
            d = datetime.fromisoformat(et[:10]).date()
        except ValueError:
            return Verdict(market, False, "STATE_MALFORMED_ACTIVE_ENTRY_TIME")
        if d < today:
            stale_active += 1

    note = ""
    if stale_active:
        note = f"STALE_ACTIVE_PRESENT={stale_active} (will be purged by runtime load_state)"

    return Verdict(market, True, "STATE_OK", note)


def _validate_mcx(repo_root: Path, market: str) -> Verdict:
    p = _state_path(repo_root, market)
    data = _load_json(p)
    if data is None:
        return Verdict(market, False, "STATE_MISSING")
    if isinstance(data, tuple):
        tag = "STATE_UNREADABLE" if data[0] == "__OSERROR__" else "STATE_CORRUPT_JSON"
        return Verdict(market, False, tag)
    if not isinstance(data, dict):
        return Verdict(market, False, "STATE_SCHEMA_INVALID")

    if data.get("product") != market:
        return Verdict(market, False, "STATE_PRODUCT_MISMATCH",
                       f"file product={data.get('product')!r}")

    try:
        from mcx.mcx_version import PRODUCT_EPOCHS
    except Exception as exc:
        return Verdict(market, False, "STATE_EPOCH_AUTHORITY_UNAVAILABLE",
                       type(exc).__name__)
    cfg = PRODUCT_EPOCHS.get(market)
    if not cfg:
        return Verdict(market, False, "STATE_PRODUCT_UNKNOWN")

    if data.get("epoch") != cfg["epoch"]:
        return Verdict(market, False, "STATE_EPOCH_MISMATCH",
                       f"{data.get('epoch')!r} != {cfg['epoch']!r}")
    if data.get("strategy_version") != cfg["strategy_version"]:
        return Verdict(market, False, "STATE_STRATEGY_VERSION_MISMATCH",
                       f"{data.get('strategy_version')!r} != {cfg['strategy_version']!r}")

    ids = data.get("_counted_trade_ids", [])
    if ids is None:
        ids = []
    if not isinstance(ids, list):
        return Verdict(market, False, "STATE_COUNTED_IDS_INVALID")
    if len(ids) != len(set(ids)):
        return Verdict(market, False, "STATE_COUNTED_IDS_DUPLICATE")

    wins = int(data.get("t1_hit_wins", 0) or 0)
    losses = int(data.get("sl_losses", 0) or 0)
    if wins < 0 or losses < 0 or len(ids) != wins + losses:
        return Verdict(market, False, "STATE_COUNTER_INCOHERENT",
                       f"ids={len(ids)} wins={wins} losses={losses}")

    active = data.get("active_position")
    if active is not None:
        if not isinstance(active, dict):
            return Verdict(market, False, "STATE_MALFORMED_ACTIVE_POSITION")
        if not active.get("trade_id") or not active.get("entry_time"):
            return Verdict(market, False, "STATE_MALFORMED_ACTIVE_POSITION")

    completed = data.get("completed_trades")
    if completed is not None and not isinstance(completed, list):
        return Verdict(market, False, "STATE_COMPLETED_TRADES_INVALID")

    note = ""
    if active is not None:
        note = "ACTIVE_POSITION_PRESENT (worker will run RECOVERY_ONLY)"
    return Verdict(market, True, "STATE_OK", note)


def validate_market(repo_root, market) -> Verdict:
    repo_root = Path(repo_root).resolve()
    market = market.upper()
    if market in INDEX_MARKETS:
        return _validate_index(repo_root, market)
    if market in MCX_MARKETS:
        return _validate_mcx(repo_root, market)
    return Verdict(market, False, "STATE_UNKNOWN_MARKET")


def validate_markets(repo_root, markets) -> dict:
    return {m.upper(): validate_market(repo_root, m.upper()) for m in markets}


if __name__ == "__main__":
    import sys
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    for v in validate_markets(root, list(_MARKET_TO_FILE_KEY)).values():
        print(f"  {v.market:12s} ok={v.ok}  reason={v.reason}  note={v.note}")
