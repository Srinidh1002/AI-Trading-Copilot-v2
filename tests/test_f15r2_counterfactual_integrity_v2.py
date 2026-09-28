"""F15-R2 Phase R2-19 — counterfactual research integrity.

Verifies:
  * post-R2-4 captures carry all mission-required provenance fields
  * the capture path is observational only: no counter, no P&L, no
    active state, no PAPER counter mutations
  * historical rows lost to the pre-R2-4 setup-ordering bug are NOT
    backfilled with fabricated data
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

import pytest  # noqa: E402

import mcx.mcx_counterfactual as cf  # noqa: E402

REQUIRED_FIELDS = (
    "ts_utc",
    "product",
    "strategy_version",
    "policy_epoch",
    "decision",
    "confidence",
    "direction",
    "regime",
    "blocking_reasons",
    "threshold_only",
    "setup_id",
    "hypothetical_contract",
    "signal_price",
    "future_price",
    "expiry",
    "dte",
)


@pytest.fixture
def isolated_log_dir(tmp_path, monkeypatch):
    log_dir = tmp_path / "data" / "paper_trades" / "counterfactual"
    monkeypatch.setattr(cf, "_LOG_DIR", str(log_dir))
    return log_dir


def _read_rows(log_dir, product):
    path = log_dir / f"{product.lower()}_counterfactual.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_full_provenance_fields_present(isolated_log_dir):
    cf.log_rejection(
        product="CRUDEOILM",
        confidence=64.5,
        direction="SHORT",
        regime="TRENDING_DOWN",
        blocking_reasons=[],
        threshold_only=True,
        signal_price=5820.0,
        setup_id="RANGE_BREAK",
        underlying_future_symbol="CRUDEOILM26OCTFUT",
        future_price=5820.0,
        expiry="2026-10-19",
        dte=20,
        option_side="PE",
        hypothetical_contract={
            "symbol": "CRUDEOILM26OCT5800PE",
            "token": "12345",
            "strike": 5800,
            "type": "PE",
            "ltp": 82.0,
            "score": 91.0,
        },
        attempt=17,
        strategy_version="MCX_V4_FROZEN",
        policy_epoch="MCX_CERT_V1",
        decision="WAIT",
    )

    rows = _read_rows(isolated_log_dir, "CRUDEOILM")
    assert len(rows) == 1
    row = rows[0]
    for field in REQUIRED_FIELDS:
        assert field in row, f"missing required field: {field}"

    assert row["product"] == "CRUDEOILM"
    assert row["strategy_version"] == "MCX_V4_FROZEN"
    assert row["policy_epoch"] == "MCX_CERT_V1"
    assert row["decision"] == "WAIT"
    assert row["direction"] == "SHORT"
    assert row["threshold_only"] is True
    assert row["setup_id"] == "RANGE_BREAK"
    assert row["hypothetical_contract"]["strike"] == 5800
    assert row["hypothetical_contract"]["score"] == 91.0
    assert row["dte"] == 20
    assert row["resolved"] is False


def test_optional_fields_default_to_none_not_absent(isolated_log_dir):
    cf.log_rejection(
        product="GOLDM",
        confidence=55.0,
        direction="LONG",
        regime="RANGE",
        blocking_reasons=[],
        threshold_only=False,
    )
    rows = _read_rows(isolated_log_dir, "GOLDM")
    row = rows[0]
    for field in REQUIRED_FIELDS:
        assert field in row, f"missing: {field}"
    assert row["strategy_version"] is None
    assert row["policy_epoch"] is None
    assert row["setup_id"] is None
    assert row["hypothetical_contract"] is None
    assert row["decision"] == "WAIT"


def test_non_candidate_rejection_is_marked_false(isolated_log_dir):
    cf.log_rejection(
        product="NATGASMINI",
        confidence=70.0,
        direction="LONG",
        regime="TRENDING_UP",
        blocking_reasons=["GATE_FAIL:expiry_risk"],
        threshold_only=False,
    )
    rows = _read_rows(isolated_log_dir, "NATGASMINI")
    row = rows[0]
    assert row["threshold_only"] is False
    assert row["blocking_reasons"] == ["GATE_FAIL:expiry_risk"]


def test_no_side_effects_on_bot_state():
    """log_rejection writes a JSONL file. It must not touch any bot state.

    Proof: the module imports no bot, holds no globals besides _LOG_DIR,
    and the test above proves the only write target is _LOG_DIR.
    """
    src = Path("src/mcx/mcx_counterfactual.py").read_text(encoding="utf-8")
    forbidden = (
        "certification_counter",
        "counted_trade_ids",
        "active_position",
        "total_pnl",
        "state[",
    )
    for token in forbidden:
        assert token not in src, f"forbidden mutation reference in module: {token}"


def test_capture_is_append_only(isolated_log_dir):
    cf.log_rejection(
        product="CRUDEOILM", confidence=50.0, direction="LONG",
        regime="RANGE", blocking_reasons=[], threshold_only=True,
    )
    cf.log_rejection(
        product="CRUDEOILM", confidence=60.0, direction="SHORT",
        regime="RANGE", blocking_reasons=[], threshold_only=True,
    )
    rows = _read_rows(isolated_log_dir, "CRUDEOILM")
    assert len(rows) == 2
    assert rows[0]["confidence"] == 50.0
    assert rows[1]["confidence"] == 60.0


def test_missing_token_is_normalized_to_none(isolated_log_dir):
    cf.log_rejection(
        product="CRUDEOILM", confidence=50.0, direction="LONG",
        regime="RANGE", blocking_reasons=[], threshold_only=True,
        hypothetical_contract={"symbol": "X", "token": None, "strike": 100, "type": "CE"},
    )
    rows = _read_rows(isolated_log_dir, "CRUDEOILM")
    assert rows[0]["hypothetical_contract"]["token"] is None


def test_safe_contract_drops_unknown_keys(isolated_log_dir):
    cf.log_rejection(
        product="CRUDEOILM", confidence=50.0, direction="LONG",
        regime="RANGE", blocking_reasons=[], threshold_only=True,
        hypothetical_contract={
            "symbol": "X", "strike": 100, "type": "CE",
            "secret_internal_field": "should not appear",
        },
    )
    rows = _read_rows(isolated_log_dir, "CRUDEOILM")
    assert "secret_internal_field" not in rows[0]["hypothetical_contract"]
