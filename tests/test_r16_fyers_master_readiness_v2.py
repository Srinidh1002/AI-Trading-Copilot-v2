from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from services.broker.fyers_master_readiness_v2 import (
    FyersMasterReadinessError,
    audit_required_master_cache,
    required_segments_for_markets,
    sync_required_master_cache,
)
from tools import preflight_and_start_five_market_paper as pf


def _option(symbol, segment, underlying, expiry, strike, option_type):
    exchange = symbol.split(":", 1)[0]
    return {
        "symbol": symbol,
        "exchange": exchange,
        "segment": segment,
        "underlying_symbol": underlying,
        "expiry": expiry,
        "strike": strike,
        "option_type": option_type,
        "lot_size": 1,
        "tick_size": 0.05,
    }


def _future(symbol, segment, underlying, expiry):
    exchange = symbol.split(":", 1)[0]
    return {
        "symbol": symbol,
        "exchange": exchange,
        "segment": segment,
        "underlying_symbol": underlying,
        "expiry": expiry,
        "lot_size": 1,
        "tick_size": 0.05,
    }


def _write_master(base: Path, segment: str, rows) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{segment}.json"
    path.write_text(
        json.dumps(
            {
                "segment": segment,
                "retrieved_at": "2026-10-05T00:00:00+00:00",
                "rows": list(rows),
            }
        ),
        encoding="utf-8",
    )
    return path


def _ready_source(base: Path):
    _write_master(
        base,
        "NSE_FO",
        [
            _option(
                "NSE:NIFTY26O0622450CE",
                "NSE_FO",
                "NIFTY",
                "2026-10-06",
                22450,
                "CE",
            ),
            _option(
                "NSE:NIFTY26O0622450PE",
                "NSE_FO",
                "NIFTY",
                "2026-10-06",
                22450,
                "PE",
            ),
        ],
    )
    _write_master(
        base,
        "BSE_FO",
        [
            _option(
                "BSE:SENSEX26O0872000CE",
                "BSE_FO",
                "SENSEX",
                "2026-10-08",
                72000,
                "CE",
            ),
            _option(
                "BSE:SENSEX26O0872000PE",
                "BSE_FO",
                "SENSEX",
                "2026-10-08",
                72000,
                "PE",
            ),
        ],
    )
    _write_master(
        base,
        "MCX_COM",
        [
            _future(
                "MCX:CRUDEOILM26OCTFUT",
                "MCX_COM",
                "CRUDEOILM",
                "2026-10-19",
            ),
            _option(
                "MCX:CRUDEOILM26OCT9500CE",
                "MCX_COM",
                "CRUDEOILM",
                "2026-10-15",
                9500,
                "CE",
            ),
            _future(
                "MCX:GOLDM26NOVFUT",
                "MCX_COM",
                "GOLDM",
                "2026-11-05",
            ),
            _option(
                "MCX:GOLDM26OCT120000CE",
                "MCX_COM",
                "GOLDM",
                "2026-10-29",
                120000,
                "CE",
            ),
            _future(
                "MCX:NATGASMINI26OCTFUT",
                "MCX_COM",
                "NATGASMINI",
                "2026-10-27",
            ),
            _option(
                "MCX:NATGASMINI26OCT400CE",
                "MCX_COM",
                "NATGASMINI",
                "2026-10-23",
                400,
                "CE",
            ),
        ],
    )


def test_required_segments_are_exact_and_deduplicated():
    assert required_segments_for_markets(
        ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
    ) == ("NSE_FO", "BSE_FO", "MCX_COM")


def test_audit_holds_missing_index_master(tmp_path):
    _write_master(
        tmp_path / "data/provider_cache/fyers_master",
        "MCX_COM",
        [
            _future(
                "MCX:CRUDEOILM26OCTFUT",
                "MCX_COM",
                "CRUDEOILM",
                "2026-10-19",
            ),
            _option(
                "MCX:CRUDEOILM26OCT9500CE",
                "MCX_COM",
                "CRUDEOILM",
                "2026-10-15",
                9500,
                "CE",
            ),
        ],
    )

    result = audit_required_master_cache(
        repo_root=tmp_path,
        markets=("NIFTY", "CRUDEOILM"),
        as_of=date(2026, 10, 5),
    )

    assert result["NIFTY"][0] is False
    assert result["NIFTY"][1] == "MASTER_MISSING:NSE_FO"
    assert result["CRUDEOILM"][0] is True


def test_audit_passes_all_five_with_current_contracts(tmp_path):
    cache = tmp_path / "data/provider_cache/fyers_master"
    _ready_source(cache)

    result = audit_required_master_cache(
        repo_root=tmp_path,
        markets=("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"),
        as_of=date(2026, 10, 5),
    )

    assert all(ok for ok, _reason in result.values())
    assert "next_expiry=2026-10-06" in result["NIFTY"][1]
    assert "next_expiry=2026-10-08" in result["SENSEX"][1]


def test_audit_rejects_stale_market_contracts(tmp_path):
    cache = tmp_path / "data/provider_cache/fyers_master"
    _write_master(
        cache,
        "NSE_FO",
        [
            _option(
                "NSE:NIFTY26S2922000CE",
                "NSE_FO",
                "NIFTY",
                "2026-09-29",
                22000,
                "CE",
            )
        ],
    )

    result = audit_required_master_cache(
        repo_root=tmp_path,
        markets=("NIFTY",),
        as_of=date(2026, 10, 5),
    )

    assert result["NIFTY"] == (False, "MASTER_NO_CURRENT_INDEX_OPTIONS")


def test_sync_validates_entire_source_before_first_replacement(tmp_path):
    repo = tmp_path / "prod"
    target = repo / "data/provider_cache/fyers_master"
    target.mkdir(parents=True)
    old = _write_master(
        target,
        "NSE_FO",
        [
            _option(
                "NSE:NIFTY26O0622450CE",
                "NSE_FO",
                "NIFTY",
                "2026-10-06",
                22450,
                "CE",
            )
        ],
    )
    before = old.read_bytes()

    source = tmp_path / "source"
    _write_master(
        source,
        "NSE_FO",
        [
            _option(
                "NSE:NIFTY26O1322500CE",
                "NSE_FO",
                "NIFTY",
                "2026-10-13",
                22500,
                "CE",
            )
        ],
    )
    # BSE_FO intentionally absent.

    with pytest.raises(FyersMasterReadinessError, match="MASTER_MISSING:BSE_FO"):
        sync_required_master_cache(
            repo_root=repo,
            source_dir=source,
            markets=("NIFTY", "SENSEX"),
            as_of=date(2026, 10, 5),
        )

    assert old.read_bytes() == before


def test_sync_installs_validated_required_segments(tmp_path):
    repo = tmp_path / "prod"
    source = tmp_path / "source"
    _ready_source(source)

    installed = sync_required_master_cache(
        repo_root=repo,
        source_dir=source,
        markets=("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"),
        as_of=date(2026, 10, 5),
    )

    assert set(installed) == {"NSE_FO", "BSE_FO", "MCX_COM"}

    result = audit_required_master_cache(
        repo_root=repo,
        markets=("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI"),
        as_of=date(2026, 10, 5),
    )
    assert all(ok for ok, _reason in result.values())


def test_preflight_summary_holds_market_when_master_gate_fails():
    markets = ("NIFTY", "SENSEX")
    all_ok = {m: (True, "OK") for m in markets}
    masters = {
        "NIFTY": (False, "MASTER_MISSING:NSE_FO"),
        "SENSEX": (True, "OK"),
    }
    locks = {"supervisor": True, "NIFTY": True, "SENSEX": True}

    ready, held = pf._summarize(
        all_ok,
        all_ok,
        masters,
        all_ok,
        all_ok,
        all_ok,
        locks,
        markets,
    )

    assert ready == ["SENSEX"]
    assert "NIFTY" in held
    assert "master: MASTER_MISSING:NSE_FO" in held["NIFTY"]
