"""F15-R2 M5 — GOLDM epoch/version bump V1 -> V2.

The StablePCR repair (commit 88583a9) changed GOLDM entry eligibility
from structurally blocked by PCR_INCOMPLETE to potentially tradeable
when the reference region has at least 5 paired listed strikes with
at least 2 on each side. That is a strategy evidence semantics change
and requires a fresh certification epoch per spec §34.

This file proves:
  * the registry is bumped for GOLDM only
  * the persisted V1 authority + state are archived, not deleted
  * the fresh V2 authority + state are valid and loadable
  * no other market epoch was modified
  * GOLDM counter is still 0 (nothing was counted under V1)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from mcx.mcx_version import (  # noqa: E402
    get_product_epochs,
    initialize_or_verify_for_product,
)

ARCHIVE = REPO / "data" / "paper_trades" / "_archive_mcx_goldm_v1_20260929"
V2_AUTH = REPO / "data" / "paper_trades" / "mcx_goldm_strategy_version.json"
V2_STATE = REPO / "data" / "paper_trades" / "mcx_goldm_experimental.json"


# ---------- registry ----------

def test_goldm_registry_is_v2():
    cfg = get_product_epochs("GOLDM")
    assert cfg["strategy_version"] == "MCX_GOLDM_PRECERT_V2"
    assert cfg["epoch"] == "GOLDM_PRECERT_V2"
    assert cfg["certification_eligible"] is True


def test_crudeoilm_epoch_unchanged():
    assert get_product_epochs("CRUDEOILM")["epoch"] == "POST_PRECISION_V4"
    assert (
        get_product_epochs("CRUDEOILM")["strategy_version"]
        == "MCX_POST_PRECISION_V4"
    )


def test_natgasmini_epoch_unchanged():
    assert (
        get_product_epochs("NATGASMINI")["epoch"]
        == "NATGASMINI_PRECERT_V1"
    )
    assert (
        get_product_epochs("NATGASMINI")["strategy_version"]
        == "MCX_NATGASMINI_PRECERT_V1"
    )


# ---------- archive ----------

def test_v1_authority_archived_intact():
    v1 = ARCHIVE / "mcx_goldm_strategy_version.json"
    assert v1.is_file()
    rec = json.loads(v1.read_text(encoding="utf-8"))
    assert rec["product"] == "GOLDM"
    assert rec["strategy_version"] == "MCX_GOLDM_PRECERT_V1"
    assert rec["epoch"] == "GOLDM_PRECERT_V1"


def test_v1_state_archived_intact():
    v1 = ARCHIVE / "mcx_goldm_experimental.json"
    assert v1.is_file()
    rec = json.loads(v1.read_text(encoding="utf-8"))
    assert rec["product"] == "GOLDM"
    assert rec["epoch"] == "GOLDM_PRECERT_V1"
    assert rec["strategy_version"] == "MCX_GOLDM_PRECERT_V1"
    assert rec.get("active_position") is None


# ---------- fresh V2 ----------

def test_v2_authority_valid():
    assert V2_AUTH.is_file()
    rec = json.loads(V2_AUTH.read_text(encoding="utf-8"))
    assert rec["product"] == "GOLDM"
    assert rec["strategy_version"] == "MCX_GOLDM_PRECERT_V2"
    assert rec["epoch"] == "GOLDM_PRECERT_V2"
    assert rec["certification_eligible"] is True


def test_v2_state_valid_and_flat():
    assert V2_STATE.is_file()
    st = json.loads(V2_STATE.read_text(encoding="utf-8"))
    assert st["product"] == "GOLDM"
    assert st["epoch"] == "GOLDM_PRECERT_V2"
    assert st["strategy_version"] == "MCX_GOLDM_PRECERT_V2"
    assert st.get("active_position") is None
    assert int(st.get("t1_hit_wins", 0) or 0) == 0
    assert int(st.get("sl_losses", 0) or 0) == 0
    assert int(st.get("total_trades", 0) or 0) == 0


def test_initialize_or_verify_goldm_is_ok(monkeypatch):
    monkeypatch.chdir(REPO)
    r = initialize_or_verify_for_product("GOLDM")
    assert r.get("status") == "OK", r


def test_initialize_or_verify_crudeoilm_still_ok(monkeypatch):
    monkeypatch.chdir(REPO)
    r = initialize_or_verify_for_product("CRUDEOILM")
    assert r.get("status") in ("OK", "INITIALIZED"), r


def test_initialize_or_verify_natgasmini_still_ok(monkeypatch):
    monkeypatch.chdir(REPO)
    r = initialize_or_verify_for_product("NATGASMINI")
    assert r.get("status") in ("OK", "INITIALIZED"), r


def test_goldm_counter_still_zero():
    st = json.loads(V2_STATE.read_text(encoding="utf-8"))
    counted = st.get("_counted_trade_ids", [])
    assert counted == []
    assert int(st.get("t1_hit_wins", 0) or 0) == 0
    assert int(st.get("sl_losses", 0) or 0) == 0
