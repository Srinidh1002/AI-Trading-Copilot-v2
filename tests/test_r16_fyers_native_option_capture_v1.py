from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from services.options.r16_fyers_native_option_capture_v1 import (
    R16FyersNativeOptionCapturePipelineV1,
    load_legacy_index_option_instruments,
)


NOW = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)
RECEIVED = datetime(2026, 10, 5, 8, 0, 1, tzinfo=UTC)


class Resolver:
    def __init__(self):
        self.calls = []

    def nearest_option_expiry(self, **kwargs):
        self.calls.append(("expiry", kwargs))
        return date(2026, 10, 6) if kwargs["market_symbol"] == "NIFTY" else date(2026, 10, 8)

    def resolve(self, **kwargs):
        self.calls.append(("resolve", kwargs))
        return {
            "provider_symbol": (
                f"NSE:{kwargs['market_symbol']}:{int(kwargs['strike'])}:"
                f"{kwargs['option_type']}"
            ),
            "provider_token": f"FY:{int(kwargs['strike'])}:{kwargs['option_type']}",
            "lot_size": 65 if kwargs["market_symbol"] == "NIFTY" else 20,
            "tick_size": 0.05,
        }


class Engine:
    def __init__(self, *, status="OK", missing_greeks=False):
        self.status = status
        self.missing_greeks = missing_greeks
        self.calls = []

    def fetch(self, expiry, atm, instruments, strike_range):
        self.calls.append((expiry, atm, instruments, strike_range))
        if self.status != "OK":
            return {
                "status": "EVIDENCE_UNAVAILABLE",
                "reason": "TEST_FAILURE",
                "request_count": 1,
                "per_contract_depth_requests": 0,
            }

        def row(option_type, premium):
            values = {
                "provider_symbol": f"NSE:NIFTY:{int(atm)}:{option_type}",
                "provider_token": f"FY:{int(atm)}:{option_type}",
                "token": f"LEGACY:{option_type}",
                "symbol": f"LEGACY:{option_type}",
                "ltp": premium,
                "bid": premium - 0.1,
                "ask": premium + 0.1,
                "volume": 5000,
                "oi": 1000,
                "change_in_open_interest": 100,
                "delta": 0.55 if option_type == "CE" else -0.45,
                "gamma": 0.001,
                "theta": -12.0,
                "vega": 8.0,
                "iv": 13.5,
            }
            if self.missing_greeks:
                values["gamma"] = None
            return values

        return {
            "status": "OK",
            "ce_data": {float(atm): row("CE", 100.0)},
            "pe_data": {float(atm): row("PE", 90.0)},
            "expected_count": 2,
            "missing_count": 0,
            "request_count": 1,
            "per_contract_depth_requests": 0,
        }


def _pipeline(*, engine=None):
    resolver = Resolver()
    engine = engine or Engine()
    pipeline = R16FyersNativeOptionCapturePipelineV1(
        engines_by_market={
            "NIFTY": engine,
            "SENSEX": Engine(),
        },
        resolver=resolver,
        instruments_by_market={
            "NIFTY": ({"symbol": "NIFTY", "token": "1"},),
            "SENSEX": ({"symbol": "SENSEX", "token": "2"},),
        },
        clock=lambda: RECEIVED,
    )
    return pipeline, resolver, engine


def test_native_capture_preserves_provider_option_analytics():
    pipeline, resolver, engine = _pipeline()

    result = pipeline.capture_option_inputs(
        underlying="NIFTY",
        spot_price=22460.0,
        option_exchange="NFO",
        strikes_each_side=5,
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert len(engine.calls) == 1
    assert engine.calls[0][0] == "06OCT2026"
    assert engine.calls[0][1] == 22450
    assert engine.calls[0][3] == 250

    assert len(result.contracts) == 2
    ce = next(row for row in result.contracts if row["option_type"] == "CE")
    assert ce["delta"] == 0.55
    assert ce["gamma"] == 0.001
    assert ce["theta"] == -12.0
    assert ce["vega"] == 8.0
    assert ce["iv"] == 13.5
    assert ce["change_in_open_interest"] == 100
    assert ce["lot_size"] == 65
    assert ce["tick_size"] == 0.05
    assert ce["provider_timestamp"] == RECEIVED
    assert (
        ce["provider_timestamp_basis"]
        == "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE_RECEIPT"
    )
    assert result.metadata["provider"] == "FYERS"
    assert result.metadata["per_contract_depth_requests"] == 0
    assert result.blockers == ()
    assert result.warnings == ()
    assert pipeline.broker_order_submission is False
    assert pipeline.live_execution_eligible is False


def test_missing_provider_greek_is_warning_not_fabricated():
    pipeline, _resolver, _engine = _pipeline(
        engine=Engine(missing_greeks=True)
    )

    result = pipeline.capture_option_inputs(
        underlying="NIFTY",
        spot_price=22460.0,
        option_exchange="NFO",
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert any(
        row["gamma"] is None
        for row in result.contracts
    )
    assert result.warnings == ("FYERS_OPTION_GREEKS_INCOMPLETE:2",)
    assert result.option_chain["greek_capture"]["state"] == "PARTIAL"


def test_native_chain_failure_is_explicit_blocker():
    pipeline, _resolver, _engine = _pipeline(
        engine=Engine(status="FAIL")
    )

    result = pipeline.capture_option_inputs(
        underlying="NIFTY",
        spot_price=22460.0,
        option_exchange="NFO",
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert result.contracts == ()
    assert result.blockers == (
        "FYERS_NATIVE_OPTION_CHAIN_TEST_FAILURE",
    )
    assert result.option_chain["integrity_validated"] is False


def test_full_analysis_is_prohibited():
    pipeline, _resolver, _engine = _pipeline()
    with pytest.raises(
        RuntimeError,
        match="R16_SHADOW_OPTION_CAPTURE_ONLY",
    ):
        pipeline.analyse()


def test_legacy_index_loader_filters_exact_markets(tmp_path):
    path = tmp_path / "instruments.json"
    path.write_text(
        json.dumps(
            [
                {
                    "symbol": "NIFTY06OCT2622450CE",
                    "token": "N1",
                    "strike": 2245000,
                    "expiry": "06OCT2026",
                    "instrumenttype": "OPTIDX",
                },
                {
                    "symbol": "BANKNIFTY06OCT2650000CE",
                    "token": "B1",
                    "strike": 5000000,
                    "expiry": "06OCT2026",
                    "instrumenttype": "OPTIDX",
                },
                {
                    "symbol": "SENSEX08OCT2672000PE",
                    "token": "S1",
                    "strike": 7200000,
                    "expiry": "08OCT2026",
                    "instrumenttype": "OPTIDX",
                },
                {
                    "symbol": "SENSEX5008OCT2630000PE",
                    "token": "S50",
                    "strike": 3000000,
                    "expiry": "08OCT2026",
                    "instrumenttype": "OPTIDX",
                },
            ]
        ),
        encoding="utf-8",
    )

    values = load_legacy_index_option_instruments(path)

    assert len(values["NIFTY"]) == 1
    assert values["NIFTY"][0]["strike"] == 22450
    assert values["NIFTY"][0]["type"] == "CE"
    assert len(values["SENSEX"]) == 1
    assert values["SENSEX"][0]["strike"] == 72000
    assert values["SENSEX"][0]["type"] == "PE"