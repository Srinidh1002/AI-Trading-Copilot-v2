from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services.broker.fyers_master_preflight_v2 import (
    check_fyers_master_authority_v2,
)


NOW = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)


def _write_master(root: Path, segment: str, rows, retrieved_at="2026-09-17T12:00:00+00:00"):
    p = root / "data" / "provider_cache" / "fyers_master" / f"{segment}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "segment": segment,
                "retrieved_at": retrieved_at,
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )


def _option(symbol, segment, underlying, expiry, strike, opt_type, exchange):
    return {
        "symbol": symbol,
        "exchange": exchange,
        "segment": segment,
        "instrument_type": "OPT",
        "underlying_symbol": underlying,
        "expiry": expiry,
        "strike": strike,
        "option_type": opt_type,
        "fyToken": "12345",
        "lot_size": 1,
        "tick_size": 0.05,
    }


def _future(symbol, underlying, expiry):
    return {
        "symbol": symbol,
        "exchange": "MCX",
        "segment": "MCX_COM",
        "instrument_type": "FUT",
        "underlying_symbol": underlying,
        "expiry": expiry,
        "fyToken": "98765",
        "lot_size": 1,
        "tick_size": 0.05,
    }


def test_missing_nse_master_holds_nifty_only(tmp_path):
    _write_master(
        tmp_path,
        "BSE_FO",
        [_option("BSE:SENSEX26O0872000CE", "BSE_FO", "SENSEX", "2026-10-08", 72000, "CE", "BSE")],
    )
    result = check_fyers_master_authority_v2(
        tmp_path,
        ("NIFTY", "SENSEX"),
        now=NOW,
    )
    assert result["NIFTY"] == (False, "FYERS_MASTER_MISSING:NSE_FO")
    assert result["SENSEX"][0] is True


def test_all_required_segments_and_markets_pass(tmp_path):
    _write_master(
        tmp_path,
        "NSE_FO",
        [_option("NSE:NIFTY26O0622450CE", "NSE_FO", "NIFTY", "2026-10-06", 22450, "CE", "NSE")],
    )
    _write_master(
        tmp_path,
        "BSE_FO",
        [_option("BSE:SENSEX26O0872000CE", "BSE_FO", "SENSEX", "2026-10-08", 72000, "CE", "BSE")],
    )
    _write_master(
        tmp_path,
        "MCX_COM",
        [
            _future("MCX:CRUDEOILM26OCTFUT", "CRUDEOILM", "2026-10-19"),
            _future("MCX:GOLDM26NOVFUT", "GOLDM", "2026-11-05"),
            _future("MCX:NATGASMINI26OCTFUT", "NATGASMINI", "2026-10-27"),
        ],
    )
    result = check_fyers_master_authority_v2(
        tmp_path,
        ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"),
        now=NOW,
    )
    assert all(ok for ok, _ in result.values())


def test_stale_master_fails_closed(tmp_path):
    _write_master(
        tmp_path,
        "NSE_FO",
        [_option("NSE:NIFTY26O0622450CE", "NSE_FO", "NIFTY", "2026-10-06", 22450, "CE", "NSE")],
        retrieved_at="2026-08-01T00:00:00+00:00",
    )
    result = check_fyers_master_authority_v2(
        tmp_path,
        ("NIFTY",),
        now=NOW,
        max_age_days=30,
    )
    assert result["NIFTY"][0] is False
    assert result["NIFTY"][1].startswith("FYERS_MASTER_STALE:NSE_FO:")


def test_future_rows_for_wrong_market_do_not_satisfy_authority(tmp_path):
    _write_master(
        tmp_path,
        "MCX_COM",
        [_future("MCX:GOLDM26NOVFUT", "GOLDM", "2026-11-05")],
    )
    result = check_fyers_master_authority_v2(
        tmp_path,
        ("CRUDEOILM", "GOLDM"),
        now=NOW,
    )
    assert result["CRUDEOILM"] == (
        False,
        "FYERS_MASTER_NO_CURRENT_DERIVATIVE:MCX_COM:CRUDEOILM",
    )
    assert result["GOLDM"][0] is True


def test_expired_derivatives_fail_closed(tmp_path):
    _write_master(
        tmp_path,
        "BSE_FO",
        [_option("BSE:SENSEX26S2472000CE", "BSE_FO", "SENSEX", "2026-09-24", 72000, "CE", "BSE")],
    )
    result = check_fyers_master_authority_v2(
        tmp_path,
        ("SENSEX",),
        now=NOW,
    )
    assert result["SENSEX"] == (
        False,
        "FYERS_MASTER_NO_CURRENT_DERIVATIVE:BSE_FO:SENSEX",
    )


def test_segment_mismatch_fails_closed(tmp_path):
    p = tmp_path / "data" / "provider_cache" / "fyers_master" / "NSE_FO.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "segment": "BSE_FO",
                "retrieved_at": "2026-09-17T12:00:00+00:00",
                "rows": [
                    _option(
                        "NSE:NIFTY26O0622450CE",
                        "NSE_FO",
                        "NIFTY",
                        "2026-10-06",
                        22450,
                        "CE",
                        "NSE",
                    )
                ],
            }
        ),
        encoding="utf-8",
    )
    result = check_fyers_master_authority_v2(
        tmp_path,
        ("NIFTY",),
        now=NOW,
    )
    assert result["NIFTY"] == (
        False,
        "FYERS_MASTER_SEGMENT_MISMATCH:NSE_FO",
    )
