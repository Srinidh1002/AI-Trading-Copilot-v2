"""Part 5 — MCX calibration workflow. All synthetic, no network, no live state."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tools import verify_mcx_fyers_execution_calibration as verifier  # noqa: E402
from tools import write_mcx_fyers_execution_calibration as writer  # noqa: E402


@pytest.fixture
def isolated_evidence(tmp_path, monkeypatch):
    ev = tmp_path / "evidence" / "mcx" / "fyers"
    ev.mkdir(parents=True, exist_ok=True)
    cfg = tmp_path / "evidence" / "mcx" / "exec_config.json"
    monkeypatch.setattr(verifier, "_EVIDENCE_DIR", ev)
    monkeypatch.setattr(writer, "_EVIDENCE_DIR", ev)
    monkeypatch.setattr(writer, "_CONFIG_PATH", cfg)
    return ev, cfg


def _write_row(fp, product, token, side, strike, age, qty_bid, qty_ask, ts_off=0, hash_suffix=""):
    row = {
        "session_id": "TEST_SESSION",
        "phase": "OBSERVATION",
        "provider": "FYERS",
        "product": product,
        "symbol": f"{product}_FUT_{strike}_{side}",
        "token": str(token),
        "expiry": "2026-12-31",
        "strike": strike,
        "side": side,
        "future_symbol": f"{product}_FUT",
        "future_token": "FUT_TOKEN",
        "future_price": 100.0,
        "ltp": 100.0,
        "oi": 12345,
        "volume": 678,
        "bid_levels": [{"price": 99.5, "quantity": qty_bid, "orders": 3}],
        "ask_levels": [{"price": 100.5, "quantity": qty_ask, "orders": 4}],
        "bid_quantities": [qty_bid],
        "ask_quantities": [qty_ask],
        "bid_orders": [3],
        "ask_orders": [4],
        "total_buy_quantity": qty_bid,
        "total_sell_quantity": qty_ask,
        "spread": 1.0,
        "depth_request_started_at": datetime.now(UTC).isoformat(),
        "depth_request_completed_at": datetime.now(UTC).isoformat(),
        "depth_received_at": datetime.now(UTC).isoformat(),
        "depth_round_trip_ms": 120.0,
        "execution_snapshot_observed_at": datetime.now(UTC).isoformat(),
        "execution_snapshot_age_seconds": 0.05,
        "depth_freshness_basis": "SYNCHRONOUS_FYERS_DEPTH_RESPONSE",
        "depth_provider_timestamp": None,
        "depth_provider_timestamp_available": False,
        "provider_last_trade_timestamp": "2026-09-24T09:55:00+00:00",
        "provider_last_trade_timestamp_raw": "1790...",
        "last_trade_age_seconds": age,
        "last_trade_timestamp_source": "DEPTH:ltt",
        "last_trade_recency_basis": "DEPTH:ltt",
        "session_status_at_collection": "OPEN",
        "local_receive_timestamp": datetime.now(UTC).isoformat(),
        "trading_unit": 10,
        "lot_size": None,
        "tick_size": 0.05,
        "quote_payload_hash": f"hash_{token}_{side}_{ts_off}{hash_suffix}",
        "sample_ordinal": ts_off,
        "collection_utc": datetime.now(UTC).isoformat(),
        "raw_shape_v1": {"top_level_keys": ["bids", "ask", "ltp"]},
        "sdk_version": None,
    }
    with open(fp, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _fill_good_evidence(ev, product="CRUDEOILM"):
    fp = ev / f"{product}_TEST.jsonl"
    for token, side, strike in [("T1", "CE", 100), ("T2", "PE", 100)]:
        for i in range(6):
            _write_row(
                fp,
                product,
                token,
                side,
                strike,
                age=5.0 + i,
                ts_off=i,
                qty_bid=10 + i,
                qty_ask=20 + i,
            )
    return fp


# ---------- verifier --------------------------------------------------------


def test_verifier_no_evidence_holds(isolated_evidence):
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert r["reason"] == "NO_EVIDENCE"


def test_verifier_good_evidence_passes(isolated_evidence):
    ev, _ = isolated_evidence
    _fill_good_evidence(ev, "CRUDEOILM")
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "PASS", r
    assert r["sample_count"] == 12


def test_verifier_rejects_wrong_provider(isolated_evidence):
    ev, _ = isolated_evidence
    fp = ev / "CRUDEOILM_X.jsonl"
    for i in range(10):
        _write_row(fp, "CRUDEOILM", "T1", "CE", 100, 5, 10 + i, 20 + i, ts_off=i)
    # Corrupt one row's provider
    lines = fp.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"FYERS"', '"ANGEL"')
    fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert any("provider" in f for f in r["failures"])


def test_verifier_rejects_empty_depth(isolated_evidence):
    ev, _ = isolated_evidence
    fp = ev / "CRUDEOILM_X.jsonl"
    for i in range(12):
        _write_row(
            fp,
            "CRUDEOILM",
            "T1" if i < 6 else "T2",
            "CE" if i < 6 else "PE",
            100,
            5,
            10 + i,
            20 + i,
            ts_off=i,
        )
    # Wipe depth on two rows
    lines = fp.read_text(encoding="utf-8").splitlines()
    for idx in (0, 1):
        row = json.loads(lines[idx])
        row["bid_levels"] = []
        lines[idx] = json.dumps(row)
    fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert any("depth" in f for f in r["failures"])


def test_verifier_rejects_constant_quantity(isolated_evidence):
    ev, _ = isolated_evidence
    fp = ev / "CRUDEOILM_X.jsonl"
    # Every quantity in every contract is the same value → no variation
    # to prove the field is a live quantity rather than a placeholder.
    for token, side in [("T1", "CE"), ("T2", "PE")]:
        for i in range(6):
            _write_row(
                fp, "CRUDEOILM", token, side, 100, age=5 + i, ts_off=i, qty_bid=10, qty_ask=10
            )
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert any("quantity" in f for f in r["failures"])


def test_verifier_rejects_few_contracts(isolated_evidence):
    ev, _ = isolated_evidence
    fp = ev / "CRUDEOILM_X.jsonl"
    for i in range(12):
        _write_row(fp, "CRUDEOILM", "T1", "CE", 100, 5 + i, 10 + i, 20 + i, ts_off=i)
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert any("contracts" in f for f in r["failures"])


def test_verifier_rejects_duplicate_hashes(isolated_evidence):
    ev, _ = isolated_evidence
    fp = ev / "CRUDEOILM_X.jsonl"
    for token, side in [("T1", "CE"), ("T2", "PE")]:
        for i in range(6):
            _write_row(
                fp,
                "CRUDEOILM",
                token,
                side,
                100,
                age=5 + i,
                ts_off=i,
                qty_bid=10 + i,
                qty_ask=20 + i,
                hash_suffix="_SAME",
            )
    # Force hash collision
    lines = fp.read_text(encoding="utf-8").splitlines()
    for idx, ln in enumerate(lines):
        row = json.loads(ln)
        row["quote_payload_hash"] = "identical"
        lines[idx] = json.dumps(row)
    fp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    r = verifier.verify_product("CRUDEOILM")
    assert r["verdict"] == "HOLD"
    assert any("hashes" in f for f in r["failures"])


def _make_pass_report(products):
    return {
        p: {
            "verdict": "PASS",
            "p95_age_seconds": 10.0,
            "sample_count": 12,
            "distinct_payload_hashes": 12,
            "verified_quantity_unit": "PROVIDER_QUANTITY",
            "quantity_unit_basis": "test fixture basis",
            "failures": [],
            "checks": {},
        }
        for p in products
    }


def _make_hold_report(products):
    return {p: {"verdict": "HOLD", "p95_age_seconds": None} for p in products}


def test_writer_refuses_on_hold_report(isolated_evidence, tmp_path, monkeypatch):
    ev, cfg = isolated_evidence
    _fill_good_evidence(ev)
    report = tmp_path / "rep.json"
    report.write_text(json.dumps(_make_hold_report(["CRUDEOILM"])), encoding="utf-8")
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 1
    assert not cfg.exists()


def test_writer_refuses_missing_product_in_report(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    _fill_good_evidence(ev)
    report = tmp_path / "rep.json"
    report.write_text(json.dumps({}), encoding="utf-8")
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 1
    assert not cfg.exists()


def test_writer_requires_evidence_file(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    # No evidence file written
    report = tmp_path / "rep.json"
    report.write_text(json.dumps(_make_pass_report(["CRUDEOILM"])), encoding="utf-8")
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 1
    assert not cfg.exists()


def test_writer_writes_schema2_on_pass(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    _fill_good_evidence(ev)
    report = tmp_path / "rep.json"
    report.write_text(json.dumps(_make_pass_report(["CRUDEOILM"])), encoding="utf-8")
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 0
    assert cfg.exists()
    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["providers"]["FYERS"]["CRUDEOILM"]["evidence_kind"] == "LIVE_MARKET_DEPTH"
    assert payload["providers"]["FYERS"]["CRUDEOILM"]["calibration_provider"] == "FYERS"
    assert payload["providers"]["FYERS"]["CRUDEOILM"]["depth_quantity_semantics_verified"] is True
    assert payload["providers"]["FYERS"]["CRUDEOILM"]["execution_freshness_calibrated"] is True
    assert payload["providers"]["FYERS"]["CRUDEOILM"]["execution_quote_max_age_seconds"] == 20
    assert payload["providers"]["FYERS"]["CRUDEOILM"]["depth_quantity_unit"] == "PROVIDER_QUANTITY"
    assert "quantity_unit_basis" in payload["providers"]["FYERS"]["CRUDEOILM"]


def test_writer_backs_up_existing_config(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    _fill_good_evidence(ev)
    # Pre-existing config with legacy shape
    cfg.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "CRUDEOILM": {"depth_quantity_semantics_verified": True},
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "rep.json"
    report.write_text(json.dumps(_make_pass_report(["CRUDEOILM"])), encoding="utf-8")
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 0
    backups = list(cfg.parent.glob("exec_config.json.bak_*"))
    assert backups, "writer must back up the pre-existing config"
    backup = json.loads(backups[0].read_text(encoding="utf-8"))
    assert backup["schema_version"] == "1.0"


def test_writer_dry_run_does_not_touch_disk(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    _fill_good_evidence(ev)
    report = tmp_path / "rep.json"
    report.write_text(json.dumps(_make_pass_report(["CRUDEOILM"])), encoding="utf-8")
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM", "--dry-run"])
    assert rc == 0
    assert not cfg.exists(), "dry-run must not write config"


def test_writer_merges_existing_providers(isolated_evidence, tmp_path):
    ev, cfg = isolated_evidence
    _fill_good_evidence(ev)
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "providers": {"ANGEL": {"CRUDEOILM": {"note": "legacy"}}},
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "rep.json"
    report.write_text(json.dumps(_make_pass_report(["CRUDEOILM"])), encoding="utf-8")
    rc = writer.main(["--report", str(report), "--products", "CRUDEOILM"])
    assert rc == 0
    payload = json.loads(cfg.read_text(encoding="utf-8"))
    assert "ANGEL" in payload["providers"]
    assert "FYERS" in payload["providers"]
