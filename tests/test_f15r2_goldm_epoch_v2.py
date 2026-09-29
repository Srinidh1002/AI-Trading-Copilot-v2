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


# ---------- current successor registry ----------


def test_goldm_registry_has_r22_successor_v3():
    cfg = get_product_epochs("GOLDM")

    assert cfg["strategy_version"] == "MCX_GOLDM_PRECERT_V3"

    assert cfg["epoch"] == "GOLDM_PRECERT_V3"

    assert cfg["certification_eligible"] is True


def test_crudeoilm_registry_has_r22_successor_v5():
    cfg = get_product_epochs("CRUDEOILM")

    assert cfg["epoch"] == "POST_PRECISION_V5"

    assert cfg["strategy_version"] == "MCX_POST_PRECISION_V5"

    assert cfg["certification_eligible"] is True


def test_natgasmini_registry_has_r22_successor_v2():
    cfg = get_product_epochs("NATGASMINI")

    assert cfg["epoch"] == "NATGASMINI_PRECERT_V2"

    assert cfg["strategy_version"] == "MCX_NATGASMINI_PRECERT_V2"

    assert cfg["certification_eligible"] is True


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


def _assert_old_authority_is_refused(
    monkeypatch,
    tmp_path,
    *,
    product,
    old_strategy,
    old_epoch,
):
    cfg = get_product_epochs(product)

    assert cfg is not None

    old_authority = tmp_path / f"{product.lower()}_old_authority.json"

    old_authority.write_text(
        json.dumps(
            {
                "product": product,
                "strategy_version": old_strategy,
                "epoch": old_epoch,
                "certification_eligible": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setitem(
        cfg,
        "version_path",
        str(old_authority),
    )

    result = initialize_or_verify_for_product(product)

    assert result["status"] == "VERSION_MISMATCH"

    assert result["stored"] == old_strategy

    assert result["current"] == cfg["strategy_version"]

    assert result["action"] == "REFUSE_TO_TRADE"


def test_old_goldm_v2_authority_is_refused(
    monkeypatch,
    tmp_path,
):
    _assert_old_authority_is_refused(
        monkeypatch,
        tmp_path,
        product="GOLDM",
        old_strategy="MCX_GOLDM_PRECERT_V2",
        old_epoch="GOLDM_PRECERT_V2",
    )


def test_old_crude_v4_authority_is_refused(
    monkeypatch,
    tmp_path,
):
    _assert_old_authority_is_refused(
        monkeypatch,
        tmp_path,
        product="CRUDEOILM",
        old_strategy="MCX_POST_PRECISION_V4",
        old_epoch="POST_PRECISION_V4",
    )


def test_old_natgasmini_v1_authority_is_refused(
    monkeypatch,
    tmp_path,
):
    _assert_old_authority_is_refused(
        monkeypatch,
        tmp_path,
        product="NATGASMINI",
        old_strategy="MCX_NATGASMINI_PRECERT_V1",
        old_epoch="NATGASMINI_PRECERT_V1",
    )


def test_goldm_counter_still_zero():
    st = json.loads(V2_STATE.read_text(encoding="utf-8"))
    counted = st.get("_counted_trade_ids", [])
    assert counted == []
    assert int(st.get("t1_hit_wins", 0) or 0) == 0
    assert int(st.get("sl_losses", 0) or 0) == 0
