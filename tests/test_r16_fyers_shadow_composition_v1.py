from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from services.options.r16_fyers_native_option_capture_v1 import (
    R16FyersNativeOptionCapturePipelineV1,
)
from services.paper_orchestration.r16_canonical_candidate_reader_v1 import (
    R16CanonicalCandidateReaderV1,
)
from services.paper_orchestration.r16_fyers_shadow_composition_v1 import (
    build_r16_fyers_shadow_readers_v1,
)

NOW = datetime(2026, 10, 5, 8, 0, 2, tzinfo=UTC)
MARKET_EPOCH = int(
    datetime(2026, 10, 5, 8, 0, 0, tzinfo=UTC).timestamp()
)


class FakeDataClient:
    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(self):
        self.quote_calls = []

    def quotes(self, data=None):
        self.quote_calls.append(dict(data or {}))
        symbol = data["symbols"]
        return {
            "s": "ok",
            "d": [
                {
                    "n": symbol,
                    "v": {
                        "symbol": symbol,
                        "lp": 22460.0 if "NIFTY" in symbol else 72000.0,
                        "tt": MARKET_EPOCH,
                        "fyToken": "INDEX",
                    },
                }
            ],
        }

    def history(self, data=None):
        return {"s": "ok", "candles": []}

    def depth(self, data=None):
        return {"s": "error", "code": -1}

    def optionchain(self, data=None):
        return {"s": "error", "code": -1}

    def futures_chain(self, data=None):
        return {"s": "error", "code": -1}


def _raw_rows():
    return [
        {
            "symbol": "NIFTY06OCT2622450CE",
            "token": "NCE",
            "strike": 2245000,
            "expiry": "06OCT2026",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
            "name": "NIFTY",
        },
        {
            "symbol": "NIFTY06OCT2622450PE",
            "token": "NPE",
            "strike": 2245000,
            "expiry": "06OCT2026",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
            "name": "NIFTY",
        },
        {
            "symbol": "SENSEX08OCT2672000CE",
            "token": "SCE",
            "strike": 7200000,
            "expiry": "08OCT2026",
            "instrumenttype": "OPTIDX",
            "exch_seg": "BFO",
            "name": "SENSEX",
        },
        {
            "symbol": "SENSEX08OCT2672000PE",
            "token": "SPE",
            "strike": 7200000,
            "expiry": "08OCT2026",
            "instrumenttype": "OPTIDX",
            "exch_seg": "BFO",
            "name": "SENSEX",
        },
    ]


def _instrument_file(tmp_path):
    path = tmp_path / "instruments.json"
    path.write_text(json.dumps(_raw_rows()), encoding="utf-8")
    return path


def test_fyers_shadow_bundle_is_data_only_and_installs_canonical_candidate(tmp_path):
    client = FakeDataClient()
    readers = build_r16_fyers_shadow_readers_v1(
        data_client=client,
        instrument_rows=_raw_rows(),
        legacy_instrument_path=_instrument_file(tmp_path),
        clock=lambda: NOW,
    )

    assert type(readers.candidate_reader) is R16CanonicalCandidateReaderV1
    assert type(readers.option_decision_pipeline) is R16FyersNativeOptionCapturePipelineV1
    assert readers.candidate_reader.mode == "SHADOW_ONLY"
    assert readers.option_decision_pipeline.mode == "SHADOW_ONLY"
    assert readers.option_decision_pipeline.broker_order_submission is False
    assert client.order_capability_allowed is False
    assert client.automatic_fallback_allowed is False


def test_fyers_shadow_quote_reader_preserves_provider_market_timestamp(tmp_path):
    client = FakeDataClient()
    readers = build_r16_fyers_shadow_readers_v1(
        data_client=client,
        instrument_rows=_raw_rows(),
        legacy_instrument_path=_instrument_file(tmp_path),
        clock=lambda: NOW,
    )

    quote = readers.quote_reader("NSE", "99926000", "NIFTY")

    assert quote["spot_price"] == 22460.0
    assert quote["market_timestamp"] == datetime.fromtimestamp(
        MARKET_EPOCH,
        tz=UTC,
    )
    assert quote["received_at"] == NOW
    assert quote["timestamp_source"] == "FYERS_QUOTES_TT"
    assert quote["provider"] == "FYERS"
    assert quote["broker_order_submission"] is False
    assert quote["live_execution_eligible"] is False
    assert client.quote_calls == [{"symbols": "NSE:NIFTY50-INDEX"}]


def test_fyers_shadow_builder_rejects_order_capable_client(tmp_path):
    class Unsafe(FakeDataClient):
        order_capability_allowed = True

    with pytest.raises(ValueError, match="order capability prohibited"):
        build_r16_fyers_shadow_readers_v1(
            data_client=Unsafe(),
            instrument_rows=_raw_rows(),
            legacy_instrument_path=_instrument_file(tmp_path),
            clock=lambda: NOW,
        )


def test_shadow_composition_source_has_no_order_submission_calls():
    from pathlib import Path

    text = Path(
        "services/paper_orchestration/"
        "r16_fyers_shadow_composition_v1.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "placeOrder(",
        "place_order(",
        "submit_order(",
        "modify_order(",
        "cancel_order(",
        "live_execution_eligible=True",
        "broker_order_submission=True",
    )
    assert all(item not in text for item in forbidden)
