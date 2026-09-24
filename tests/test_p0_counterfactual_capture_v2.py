"""Part 13 — threshold-only counterfactual capture. No provider, no live data."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from mcx import mcx_counterfactual as cf


@pytest.fixture
def isolated_dir(tmp_path, monkeypatch):
    d = tmp_path / "counterfactual"
    monkeypatch.setattr(cf, "_LOG_DIR", str(d))
    return d


def test_log_rejection_writes_per_product_file(isolated_dir):
    cf.log_rejection(
        product="CRUDEOILM",
        confidence=62.5,
        direction="LONG",
        regime="TREND_UP",
        blocking_reasons=[],
        threshold_only=True,
        signal_price=6900.0,
        setup_id="LONG_CONTINUATION",
        underlying_future_symbol="CRUDEOILM_FUT",
        future_price=6900.0,
        expiry="2026-12-31",
        dte=15,
        option_side="CE",
        hypothetical_contract={
            "symbol": "CRUDEOILM_7000CE",
            "token": "12345",
            "strike": 7000,
            "type": "CE",
            "ltp": 120.5,
            "score": 0.81,
        },
        attempt=17,
    )
    p = isolated_dir / "crudeoilm_counterfactual.jsonl"
    assert p.exists()
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    r = rows[0]
    assert r["product"] == "CRUDEOILM"
    assert r["confidence"] == 62.5
    assert r["threshold_only"] is True
    assert r["hypothetical_contract"]["symbol"] == "CRUDEOILM_7000CE"
    assert r["hypothetical_contract"]["strike"] == 7000
    assert r["hypothetical_contract"]["type"] == "CE"
    assert r["option_side"] == "CE"
    assert r["dte"] == 15
    assert r["resolved"] is False


def test_files_are_per_product_isolated(isolated_dir):
    cf.log_rejection(
        product="CRUDEOILM", confidence=55, direction="LONG", regime="RANGE",
        blocking_reasons=[], threshold_only=True,
    )
    cf.log_rejection(
        product="GOLDM", confidence=58, direction="SHORT", regime="RANGE",
        blocking_reasons=[], threshold_only=True,
    )
    assert (isolated_dir / "crudeoilm_counterfactual.jsonl").exists()
    assert (isolated_dir / "goldm_counterfactual.jsonl").exists()
    assert not (isolated_dir / "crudeoilm_counterfactual.jsonl").samefile(
        isolated_dir / "goldm_counterfactual.jsonl"
    )


def test_non_threshold_only_is_recorded_but_flagged(isolated_dir):
    cf.log_rejection(
        product="NATGASMINI", confidence=45, direction="LONG", regime="RANGE",
        blocking_reasons=["EVENT_RISK_..._BLOCKS"], threshold_only=False,
    )
    p = isolated_dir / "natgasmini_counterfactual.jsonl"
    row = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert row["threshold_only"] is False
    assert row["blocking_reasons"] == ["EVENT_RISK_..._BLOCKS"]


def test_hypothetical_contract_null_is_allowed(isolated_dir):
    cf.log_rejection(
        product="GOLDM", confidence=60, direction="LONG", regime="RANGE",
        blocking_reasons=[], threshold_only=True,
        hypothetical_contract=None,
    )
    row = json.loads((isolated_dir / "goldm_counterfactual.jsonl").read_text(
        encoding="utf-8").splitlines()[0])
    assert row["hypothetical_contract"] is None


def test_append_only_multiple_rows(isolated_dir):
    for c in (55, 60, 65):
        cf.log_rejection(
            product="CRUDEOILM", confidence=c, direction="LONG", regime="RANGE",
            blocking_reasons=[], threshold_only=True,
        )
    rows = (isolated_dir / "crudeoilm_counterfactual.jsonl").read_text(
        encoding="utf-8").strip().splitlines()
    assert len(rows) == 3
    assert [json.loads(r)["confidence"] for r in rows] == [55.0, 60.0, 65.0]


def test_safe_contract_strips_unexpected_fields(isolated_dir):
    cf.log_rejection(
        product="GOLDM", confidence=60, direction="LONG", regime="RANGE",
        blocking_reasons=[], threshold_only=True,
        hypothetical_contract={
            "symbol": "GOLDM_1", "token": "999", "strike": 100, "type": "CE",
            "ltp": 5.5, "score": 0.7,
            "FYERS_ACCESS_TOKEN": "SHOULD_NOT_APPEAR",
            "secret": "nope",
        },
    )
    row = json.loads((isolated_dir / "goldm_counterfactual.jsonl").read_text(
        encoding="utf-8").splitlines()[0])
    hc = row["hypothetical_contract"]
    assert "FYERS_ACCESS_TOKEN" not in hc
    assert "secret" not in hc
    assert set(hc.keys()) <= {"symbol", "token", "strike", "type", "ltp", "score"}


def test_direction_side_mapping_consistent(isolated_dir):
    cf.log_rejection(
        product="CRUDEOILM", confidence=60, direction="SHORT", regime="TREND_DOWN",
        blocking_reasons=[], threshold_only=True, option_side="PE",
        hypothetical_contract={"symbol": "X", "token": "1", "strike": 100, "type": "PE"},
    )
    row = json.loads((isolated_dir / "crudeoilm_counterfactual.jsonl").read_text(
        encoding="utf-8").splitlines()[0])
    assert row["direction"] == "SHORT"
    assert row["option_side"] == "PE"
    assert row["hypothetical_contract"]["type"] == "PE"


def test_old_shared_file_is_not_written_by_new_code(isolated_dir, tmp_path):
    """The new module must never write the old shared path."""
    old_path = tmp_path / "mcx_counterfactual.jsonl"
    cf.log_rejection(
        product="CRUDEOILM", confidence=60, direction="LONG", regime="RANGE",
        blocking_reasons=[], threshold_only=True,
    )
    assert not old_path.exists()


def test_module_source_has_no_shared_log_constant():
    src = (REPO / "src" / "mcx" / "mcx_counterfactual.py").read_text(encoding="utf-8")
    # The old shared-file name must not survive in the new module.
    assert "mcx_counterfactual.jsonl" not in src or "counterfactual/" in src
    # Per-product file naming must be present.
    assert "_counterfactual.jsonl" in src


def test_mcx_paper_bot_call_site_passes_threshold_only():
    src = (REPO / "src" / "mcx" / "mcx_paper_bot.py").read_text(encoding="utf-8")
    assert "threshold_only=_threshold_only" in src
    assert "hypothetical_contract=_hyp_contract" in src
    # No extra provider call in the capture block.
    capture_idx = src.find("threshold_only=_threshold_only")
    slice_ = src[max(0, capture_idx - 800):capture_idx + 200]
    assert "fetch_execution_quote" not in slice_
    assert "getMarketData" not in slice_
