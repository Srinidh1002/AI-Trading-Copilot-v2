"""Part 4 — strict MCX calibration gate. Fixtures only, no live config."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tools import preflight_and_start_five_market_paper as pf


def _stub(monkeypatch, status):
    monkeypatch.setattr(pf, "_calibration_status_for", lambda product: status)


def _valid_status():
    return {
        "product": "CRUDEOILM",
        "provider": "FYERS",
        "calibration_provider": "FYERS",
        "provider_scoped": True,
        "calibration_valid": True,
        "quantity_verified": True,
        "freshness_calibrated": True,
        "max_age_seconds": 30,
        "entry_execution_calibrated": True,
        "evidence_kind": "LIVE_MARKET_DEPTH",
        "reason": "OK",
    }


def test_valid_full_calibration_passes(monkeypatch):
    _stub(monkeypatch, _valid_status())
    out = pf.check_calibration(("CRUDEOILM",))
    assert out["CRUDEOILM"][0] is True
    assert out["CRUDEOILM"][1] == "calibrated"


def test_quantity_false_holds(monkeypatch):
    s = _valid_status()
    s["quantity_verified"] = False
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "quantity_verified" in why


def test_freshness_false_holds(monkeypatch):
    s = _valid_status()
    s["freshness_calibrated"] = False
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "freshness_calibrated" in why


def test_entry_execution_false_holds(monkeypatch):
    s = _valid_status()
    s["entry_execution_calibrated"] = False
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "entry_execution_calibrated" in why


def test_provider_scoped_false_holds(monkeypatch):
    s = _valid_status()
    s["provider_scoped"] = False
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "provider_scoped" in why


def test_calibration_valid_false_holds(monkeypatch):
    s = _valid_status()
    s["calibration_valid"] = False
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "calibration_valid" in why


def test_wrong_evidence_kind_holds(monkeypatch):
    s = _valid_status()
    s["evidence_kind"] = "SYNTHETIC"
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "EVIDENCE_KIND" in why


def test_missing_evidence_kind_holds(monkeypatch):
    s = _valid_status()
    s["evidence_kind"] = None
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "EVIDENCE_KIND" in why


def test_provider_mismatch_holds(monkeypatch):
    s = _valid_status()
    s["calibration_provider"] = "ANGEL"
    _stub(monkeypatch, s)
    ok, why = pf.check_calibration(("CRUDEOILM",))["CRUDEOILM"]
    assert ok is False
    assert "PROVIDER_MISMATCH" in why


def test_all_three_mcx_use_strict_gate(monkeypatch):
    """Each product independently must satisfy every flag."""
    def _per_product(product):
        base = _valid_status()
        base["product"] = product
        if product == "GOLDM":
            base["quantity_verified"] = False
        if product == "NATGASMINI":
            base["provider_scoped"] = False
        return base
    monkeypatch.setattr(pf, "_calibration_status_for", _per_product)
    out = pf.check_calibration(("CRUDEOILM", "GOLDM", "NATGASMINI"))
    assert out["CRUDEOILM"][0] is True
    assert out["GOLDM"][0] is False and "quantity_verified" in out["GOLDM"][1]
    assert out["NATGASMINI"][0] is False and "provider_scoped" in out["NATGASMINI"][1]


def test_index_markets_unaffected(monkeypatch):
    def _never(*_a, **_k):
        raise AssertionError("calibration must not be probed for index markets")
    monkeypatch.setattr(pf, "_calibration_status_for", _never)
    out = pf.check_calibration(("NIFTY", "SENSEX"))
    assert out["NIFTY"] == (True, "n/a (index)")
    assert out["SENSEX"] == (True, "n/a (index)")
