"""F15 — native depth extraction, provider ltt evidence, writer unit propagation.

Option D aligned. Tests only reference the current collector API.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tools import collect_mcx_fyers_execution_calibration as collector  # noqa: E402
from tools import verify_mcx_fyers_execution_calibration as verifier  # noqa: E402
from tools import write_mcx_fyers_execution_calibration as writer  # noqa: E402

# --- _extract_depth variants ----------------------------------------------


def test_extract_depth_buy_sell_shape():
    row = {
        "depth": {
            "buy": [{"price": 99.5, "quantity": 10, "orders": 2}],
            "sell": [{"price": 100.5, "quantity": 20, "orders": 3}],
        }
    }
    bids, asks = collector._extract_depth(row)
    assert len(bids) == 1 and len(asks) == 1
    assert bids[0]["quantity"] == 10
    assert asks[0]["quantity"] == 20


def test_extract_depth_best_five_fallback():
    row = {
        "bestFiveBuyData": [{"price": 99.5, "quantity": 10}],
        "bestFiveSellData": [{"price": 100.5, "quantity": 20}],
    }
    bids, asks = collector._extract_depth(row)
    assert len(bids) == 1 and len(asks) == 1


def test_extract_depth_returns_empty_when_no_depth():
    bids, asks = collector._extract_depth({"ltp": 100})
    assert bids == [] and asks == []


def test_level_quantity_variants():
    assert collector._level_quantity({"quantity": 5}) == 5
    assert collector._level_quantity({"volume": 7}) == 7
    assert collector._level_quantity({"qty": 9}) == 9
    assert collector._level_quantity({}) is None


def test_level_orders_variants():
    assert collector._level_orders({"orders": 3}) == 3
    assert collector._level_orders({"ord": 4}) == 4
    assert collector._level_orders({}) is None


# --- provider ltt extraction ----------------------------------------------


def test_provider_ltt_from_depth_top_level():
    v = collector._provider_ltt_from_depth({"ltt": 1790359088})
    assert v == 1790359088


def test_provider_ltt_from_depth_nested():
    v = collector._provider_ltt_from_depth({"depth": {"ltt": 1790359088}})
    assert v == 1790359088


def test_provider_ltt_from_depth_missing():
    assert collector._provider_ltt_from_depth({"ltp": 100}) is None


# --- _parse_provider_ts ---------------------------------------------------


def test_parse_provider_ts_epoch_seconds():
    dt = collector._parse_provider_ts(1790359088)
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_provider_ts_epoch_seconds_string():
    dt = collector._parse_provider_ts("1790359088")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_provider_ts_epoch_millis():
    dt = collector._parse_provider_ts(1790359088000)
    assert dt is not None


def test_parse_provider_ts_iso_string():
    dt = collector._parse_provider_ts("2026-09-28T10:00:00+00:00")
    assert dt is not None
    assert dt.year == 2026


def test_parse_provider_ts_iso_z():
    dt = collector._parse_provider_ts("2026-09-28T03:00:00Z")
    assert dt is not None


def test_parse_provider_ts_unparsable_returns_none():
    assert collector._parse_provider_ts("banana") is None
    assert collector._parse_provider_ts("") is None
    assert collector._parse_provider_ts(None) is None


# --- verifier gates -------------------------------------------------------


@pytest.fixture
def isolated_evidence(tmp_path, monkeypatch):
    ev = tmp_path / "evidence" / "mcx" / "fyers"
    ev.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "evidence" / "mcx" / "exec_config.json"
    monkeypatch.setattr(verifier, "_EVIDENCE_DIR", ev)
    monkeypatch.setattr(writer, "_EVIDENCE_DIR", ev)
    monkeypatch.setattr(writer, "_CONFIG_PATH", cfg)
    return ev, cfg


def _row(product, token, side, *, expiry="2026-12-31", qty_bid=10, qty_ask=20, ordinal=0):
    now = datetime.now(UTC).isoformat()
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
        "depth_round_trip_ms": 100.0,
        "execution_snapshot_observed_at": now,
        "execution_snapshot_age_seconds": 0.05,
        "depth_freshness_basis": "SYNCHRONOUS_FYERS_DEPTH_RESPONSE",
        "depth_provider_timestamp": None,
        "depth_provider_timestamp_available": False,
        "provider_last_trade_timestamp": None,
        "provider_last_trade_timestamp_raw": None,
        "last_trade_age_seconds": 5.0 + ordinal,
        "last_trade_timestamp_source": "DEPTH:ltt",
        "last_trade_recency_basis": "DEPTH:ltt",
        "session_status_at_collection": "OPEN",
        "local_receive_timestamp": now,
        "quote_payload_hash": f"h_{token}_{side}_{ordinal}",
        "sample_ordinal": ordinal,
        "collection_utc": now,
    }


def _write_rows(ev, product, rows):
    fp = ev / f"{product}_T.jsonl"
    with open(fp, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_verifier_requires_both_ce_and_pe(isolated_evidence):
    ev, _ = isolated_evidence
    rows = [_row("CRUDEOILM", "T1", "CE", ordinal=i) for i in range(12)]
    _write_rows(ev, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert any("ce_pe" in f for f in r["failures"])


def test_verifier_requires_single_expiry(isolated_evidence):
    ev, _ = isolated_evidence
    rows = [_row("CRUDEOILM", "T1", "CE", ordinal=i) for i in range(3)]
    rows += [_row("CRUDEOILM", "T1", "CE", expiry="2027-01-15", ordinal=i + 100) for i in range(3)]
    rows += [_row("CRUDEOILM", "T2", "PE", ordinal=i + 200) for i in range(6)]
    _write_rows(ev, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert any("expiry" in f for f in r["failures"])


def test_verifier_rejects_non_open_session(isolated_evidence):
    ev, _ = isolated_evidence
    rows = []
    for tok, side in (("T1", "CE"), ("T2", "PE")):
        for i in range(6):
            row = _row("CRUDEOILM", tok, side, ordinal=i, qty_bid=10 + i, qty_ask=20 + i)
            row["session_status_at_collection"] = "CLOSED"
            rows.append(row)
    _write_rows(ev, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert "session_open" in r["failures"]


def test_verifier_pass_emits_provider_quantity(isolated_evidence):
    ev, _ = isolated_evidence
    rows = []
    for tok, side in (("T1", "CE"), ("T2", "PE")):
        for i in range(6):
            rows.append(_row("CRUDEOILM", tok, side, ordinal=i, qty_bid=10 + i, qty_ask=20 + i))
    _write_rows(ev, "CRUDEOILM", rows)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "PASS", r
    assert r["verified_quantity_unit"] == "PROVIDER_QUANTITY"
    basis = r["quantity_unit_basis"]
    assert isinstance(basis, str) and len(basis) > 30


# --- writer unit propagation ----------------------------------------------


def test_writer_refuses_without_verified_unit(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    _write_rows(ev, "CRUDEOILM", [_row("CRUDEOILM", "T1", "CE", ordinal=0)])
    report = tmp_path / "r.json"
    report.write_text(
        json.dumps({"CRUDEOILM": {"verdict": "PASS", "p95_age_seconds": 10.0}}), encoding="utf-8"
    )
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 1
    assert not cfg.exists()


def test_writer_uses_verified_unit_not_lots(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    _write_rows(ev, "CRUDEOILM", [_row("CRUDEOILM", "T1", "CE", ordinal=0)])
    report = tmp_path / "r.json"
    report.write_text(
        json.dumps(
            {
                "CRUDEOILM": {
                    "verdict": "PASS",
                    "p95_age_seconds": 10.0,
                    "verified_quantity_unit": "PROVIDER_QUANTITY",
                    "quantity_unit_basis": "sdk has no lot proof",
                }
            }
        ),
        encoding="utf-8",
    )
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 0
    payload = json.loads(cfg.read_text(encoding="utf-8"))
    rec = payload["providers"]["FYERS"]["CRUDEOILM"]
    assert rec["depth_quantity_unit"] == "PROVIDER_QUANTITY"
    assert rec["depth_quantity_unit"] != "LOTS"
    assert "quantity_unit_basis" in rec


# --- normalizer raw_shape_v1 ---------------------------------------------


def test_normalizer_emits_raw_shape():
    from services.broker.fyers_response_normalizer_v2 import (
        normalize_full_market_data,
    )

    response = {
        "s": "ok",
        "d": {
            "MCX:CRUDEOILM26OCT8800CE": {
                "ltp": 12.5,
                "bids": [{"price": 12.4, "quantity": 5, "ord": 2}],
                "ask": [{"price": 12.6, "quantity": 7, "ord": 3}],
            }
        },
    }
    out = normalize_full_market_data(
        response,
        provider_symbol="MCX:CRUDEOILM26OCT8800CE",
        symboltoken="TOK",
    )
    row = out["data"]["fetched"][0]
    assert "raw_shape_v1" in row
    assert "ltp" in row["raw_shape_v1"]["top_level_keys"]
