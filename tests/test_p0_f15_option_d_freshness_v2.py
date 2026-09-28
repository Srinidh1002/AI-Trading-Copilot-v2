"""F15 Option D — depth-snapshot freshness vs last-trade recency."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tools import verify_mcx_fyers_execution_calibration as verifier  # noqa: E402


@pytest.fixture
def isolated_evidence(tmp_path, monkeypatch):
    ev = tmp_path / "ev"
    ev.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(verifier, "_EVIDENCE_DIR", ev)
    return ev


def _row(product, token, side, *, ordinal, session="OPEN", rtt_ms=100.0,
         snap_age=0.05, lt_age=None, lt_src="DEPTH:ltt",
         qty_bid=10, qty_ask=20, expiry="2026-12-31"):
    import datetime as _dt
    now = _dt.datetime.now(_dt.UTC).isoformat()
    return {
        "session_id": "T",
        "phase": "OBSERVATION",
        "provider": "FYERS",
        "product": product,
        "token": token,
        "expiry": expiry,
        "strike": 100,
        "side": side,
        "bid_levels": [{"price": 99.5, "quantity": qty_bid, "orders": 2}],
        "ask_levels": [{"price": 100.5, "quantity": qty_ask, "orders": 3}],
        "bid_quantities": [qty_bid],
        "ask_quantities": [qty_ask],
        "depth_request_started_at": now,
        "depth_request_completed_at": now,
        "depth_received_at": now,
        "depth_round_trip_ms": rtt_ms,
        "execution_snapshot_observed_at": now,
        "execution_snapshot_age_seconds": snap_age,
        "depth_freshness_basis": "SYNCHRONOUS_FYERS_DEPTH_RESPONSE",
        "depth_provider_timestamp": None,
        "depth_provider_timestamp_available": False,
        "provider_last_trade_timestamp": None if lt_age is None else now,
        "provider_last_trade_timestamp_raw": None,
        "last_trade_age_seconds": lt_age,
        "last_trade_timestamp_source": lt_src if lt_age is not None else None,
        "last_trade_recency_basis": lt_src if lt_age is not None else "UNAVAILABLE",
        "session_status_at_collection": session,
        "local_receive_timestamp": now,
        "quote_payload_hash": f"h_{token}_{side}_{ordinal}",
        "sample_ordinal": ordinal,
        "collection_utc": now,
    }


def _write(ev, product, rows):
    fp = ev / f"{product}_T.jsonl"
    with open(fp, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _good(ev, product="CRUDEOILM", lt_age=None):
    rows = []
    for tok, side in (("T1", "CE"), ("T2", "PE")):
        for i in range(6):
            rows.append(_row(product, tok, side, ordinal=i,
                             qty_bid=10 + i, qty_ask=20 + i,
                             lt_age=lt_age))
    _write(ev, product, rows)


def test_pass_without_last_trade_age(isolated_evidence):
    """A fresh depth snapshot is valid even when last trade is old."""
    _good(isolated_evidence, lt_age=15000.0)  # > 4 hours old
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "PASS", r
    assert r["reported"]["LAST_TRADE_AGE_P95"] is not None
    assert r["last_trade_recency_basis"] == "DEPTH:ltt"


def test_fail_when_session_not_open(isolated_evidence):
    rows = []
    for tok, side in (("T1", "CE"), ("T2", "PE")):
        for i in range(6):
            rows.append(_row("CRUDEOILM", tok, side, ordinal=i,
                             session="CLOSED", qty_bid=10+i, qty_ask=20+i))
    _write(isolated_evidence, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert "session_open" in r["failures"]


def test_fail_when_rtt_exceeds_cap(isolated_evidence):
    rows = []
    for tok, side in (("T1", "CE"), ("T2", "PE")):
        for i in range(6):
            rows.append(_row("CRUDEOILM", tok, side, ordinal=i,
                             rtt_ms=20000.0, qty_bid=10+i, qty_ask=20+i))
    _write(isolated_evidence, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert "depth_rtt" in r["failures"]


def test_fail_when_snapshot_age_exceeds_cap(isolated_evidence):
    rows = []
    for tok, side in (("T1", "CE"), ("T2", "PE")):
        for i in range(6):
            rows.append(_row("CRUDEOILM", tok, side, ordinal=i,
                             snap_age=30.0, qty_bid=10+i, qty_ask=20+i))
    _write(isolated_evidence, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert "snapshot_age" in r["failures"]


def test_provider_depth_timestamp_available_false_by_default(isolated_evidence):
    _good(isolated_evidence)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "PASS"
    assert r["reported"]["PROVIDER_DEPTH_TIMESTAMP_AVAILABLE"] is False
    assert r["depth_freshness_basis"] == "SYNCHRONOUS_FYERS_DEPTH_RESPONSE"


def test_deprecated_freshness_fields_do_not_gate(isolated_evidence):
    """An old-style age_seconds=9999 must not cause a HOLD."""
    rows = []
    for tok, side in (("T1", "CE"), ("T2", "PE")):
        for i in range(6):
            r = _row("CRUDEOILM", tok, side, ordinal=i,
                     qty_bid=10+i, qty_ask=20+i)
            r["age_seconds"] = 9999.0  # legacy field
            rows.append(r)
    _write(isolated_evidence, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "PASS", r
