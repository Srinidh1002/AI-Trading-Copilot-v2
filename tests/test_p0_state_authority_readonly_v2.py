"""Part 3 — strict read-only state authority for preflight. Synthetic fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from services.paper_orchestration.state_authority_readonly_v2 import (
    INDEX_STRATEGY_VERSION,
    INDEX_CERTIFICATION_EPOCH,
    validate_market,
)


def _write_index_state(root: Path, market: str, **overrides):
    key = market.lower()
    payload = {
        "market": market,
        "strategy_version": INDEX_STRATEGY_VERSION,
        "certification_epoch": INDEX_CERTIFICATION_EPOCH,
        "certification_counter": 3,
        "counted_trade_ids": ["T1", "T2", "T3"],
        "certification_wins": 0,
        "certification_losses": 3,
        "active_trades": [],
        "orphaned_trades": [],
        "completed_trades": [],
    }
    payload.update(overrides)
    p = root / "data" / "paper_trades" / f"{key}_experimental.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _write_mcx_state(root: Path, market: str, **overrides):
    key = {"CRUDEOILM": "mcx_crudeoilm",
           "GOLDM": "mcx_goldm",
           "NATGASMINI": "mcx_natgasmini"}[market]
    from mcx.mcx_version import PRODUCT_EPOCHS
    cfg = PRODUCT_EPOCHS[market]
    payload = {
        "product": market,
        "epoch": cfg["epoch"],
        "strategy_version": cfg["strategy_version"],
        "_counted_trade_ids": [],
        "t1_hit_wins": 0,
        "sl_losses": 0,
        "total_trades": 0,
        "completed_trades": [],
        "active_position": None,
    }
    payload.update(overrides)
    p = root / "data" / "paper_trades" / f"{key}_experimental.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# ---------- INDEX cases -----------------------------------------------------

def test_index_valid(tmp_path):
    _write_index_state(tmp_path, "NIFTY")
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is True
    assert v.reason == "STATE_OK"


def test_index_missing(tmp_path):
    (tmp_path / "data" / "paper_trades").mkdir(parents=True)
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is False
    assert v.reason == "STATE_MISSING"


def test_index_corrupt(tmp_path):
    p = tmp_path / "data" / "paper_trades" / "nifty_experimental.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{bad", encoding="utf-8")
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is False
    assert v.reason == "STATE_CORRUPT_JSON"


def test_index_wrong_epoch(tmp_path):
    _write_index_state(tmp_path, "NIFTY", certification_epoch="WRONG_EPOCH")
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is False
    assert v.reason == "STATE_EPOCH_MISMATCH"


def test_index_wrong_version(tmp_path):
    _write_index_state(tmp_path, "NIFTY", strategy_version="WRONG_VERSION")
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is False
    assert v.reason == "STATE_STRATEGY_VERSION_MISMATCH"


def test_index_counter_mismatch(tmp_path):
    _write_index_state(tmp_path, "NIFTY", certification_counter=5)
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is False
    assert v.reason == "STATE_COUNTER_INCOHERENT"


def test_index_duplicate_ids(tmp_path):
    _write_index_state(tmp_path, "NIFTY",
                       certification_counter=2,
                       counted_trade_ids=["T1", "T1"],
                       certification_wins=0,
                       certification_losses=2)
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is False
    assert v.reason == "STATE_COUNTED_IDS_DUPLICATE"


def test_index_malformed_active(tmp_path):
    _write_index_state(tmp_path, "NIFTY", active_trades=[{"symbol": "X"}])
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is False
    assert v.reason == "STATE_MALFORMED_ACTIVE_TRADE"


def test_index_valid_active_today(tmp_path):
    from datetime import datetime
    today_iso = datetime.now().isoformat()
    _write_index_state(tmp_path, "NIFTY", active_trades=[
        {"trade_id": "T-live", "entry_time": today_iso}
    ])
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is True
    assert v.note == ""


def test_index_stale_active_reports_note_but_ok(tmp_path):
    _write_index_state(tmp_path, "NIFTY", active_trades=[
        {"trade_id": "T-old", "entry_time": "2025-01-01T10:00:00"}
    ])
    v = validate_market(tmp_path, "NIFTY")
    assert v.ok is True
    assert "STALE_ACTIVE_PRESENT=1" in v.note


# ---------- MCX cases -------------------------------------------------------

def test_mcx_valid(tmp_path):
    _write_mcx_state(tmp_path, "CRUDEOILM")
    v = validate_market(tmp_path, "CRUDEOILM")
    assert v.ok is True
    assert v.reason == "STATE_OK"


def test_mcx_wrong_product(tmp_path):
    _write_mcx_state(tmp_path, "CRUDEOILM", product="GOLDM")
    v = validate_market(tmp_path, "CRUDEOILM")
    assert v.ok is False
    assert v.reason == "STATE_PRODUCT_MISMATCH"


def test_mcx_wrong_epoch(tmp_path):
    _write_mcx_state(tmp_path, "CRUDEOILM", epoch="WRONG")
    v = validate_market(tmp_path, "CRUDEOILM")
    assert v.ok is False
    assert v.reason == "STATE_EPOCH_MISMATCH"


def test_mcx_malformed_active_position(tmp_path):
    _write_mcx_state(tmp_path, "GOLDM", active_position={"symbol": "X"})
    v = validate_market(tmp_path, "GOLDM")
    assert v.ok is False
    assert v.reason == "STATE_MALFORMED_ACTIVE_POSITION"


def test_mcx_counter_incoherent(tmp_path):
    _write_mcx_state(tmp_path, "GOLDM",
                     _counted_trade_ids=["A"],
                     t1_hit_wins=0, sl_losses=0)
    v = validate_market(tmp_path, "GOLDM")
    assert v.ok is False
    assert v.reason == "STATE_COUNTER_INCOHERENT"


# ---------- preflight integration ------------------------------------------

def test_preflight_state_check_honors_repo_root(tmp_path):
    """The check must read from the supplied repo_root, not REPO_DEFAULT."""
    from tools import preflight_and_start_five_market_paper as pf
    _write_index_state(tmp_path, "NIFTY")
    out = pf.check_state_authority(("NIFTY",), tmp_path)
    assert out["NIFTY"][0] is True
    # A different repo_root that has no state must fail
    empty = tmp_path / "empty"
    empty.mkdir()
    out2 = pf.check_state_authority(("NIFTY",), empty)
    assert out2["NIFTY"][0] is False
