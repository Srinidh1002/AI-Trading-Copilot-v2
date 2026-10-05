from __future__ import annotations

from datetime import datetime, timezone

from services.options.fyers_certified_option_capture_v2 import (
    FyersCertifiedOptionCaptureV2,
)


NOW = datetime(2026, 10, 5, 5, 0, tzinfo=timezone.utc)
RECEIVED = datetime(2026, 10, 5, 5, 0, 1, tzinfo=timezone.utc)


class Resolver:
    def resolve(self, **kwargs):
        if kwargs["instrument_type"] == "UNDERLYING":
            return {"provider_symbol": "NSE:NIFTY50-INDEX"}
        strike = int(float(kwargs["strike"]))
        option_type = kwargs["option_type"]
        return {
            "provider_symbol": f"NSE:NIFTY26O06{strike}{option_type}",
            "provider_token": f"FY-{strike}-{option_type}",
            "lot_size": 65,
            "tick_size": 0.05,
            "metadata_status": "VERIFIED",
        }


class Provider:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = rows if rows is not None else [
            {
                "symbol": "NSE:NIFTY26O0622450CE",
                "strike": 22450.0,
                "type": "CE",
                "ltp": 120.0,
                "bid": 119.5,
                "ask": 120.0,
                "oi": 1000,
                "oich": 25,
                "volume": 5000,
                "expiry": "2026-10-06",
            },
            {
                "symbol": "NSE:NIFTY26O0622450PE",
                "strike": 22450.0,
                "type": "PE",
                "ltp": 110.0,
                "bid": 109.5,
                "ask": 110.0,
                "oi": 1200,
                "oich": -10,
                "volume": 6000,
                "expiry": "2026-10-06",
            },
        ]

    def get_option_chain(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "provider": "FYERS",
            "rows": tuple(self.rows),
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "expiry_data": (
                {"date": "2026-10-06", "expiry": 1791239400},
            ),
            "response_received_at": RECEIVED,
            "timestamp_basis": "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE",
        }


def build(rows=None):
    provider = Provider(rows)
    adapter = FyersCertifiedOptionCaptureV2(
        market="NIFTY",
        provider=provider,
        resolver=Resolver(),
        clock=lambda: NOW,
    )
    return provider, adapter


def test_fyers_certified_capture_projects_exact_verified_contracts():
    provider, adapter = build()

    result = adapter.capture_option_inputs(
        underlying="NIFTY",
        spot_price=22460.0,
        option_exchange="NFO",
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert len(provider.calls) == 1
    assert result.blockers == ()
    assert result.metadata["provider_name"] == "FYERS"
    assert (
        result.metadata["timestamp_basis"]
        == "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE"
    )
    assert result.metadata["response_received_at"] == RECEIVED
    assert len(result.contracts) == 2
    ce = next(
        item for item in result.contracts
        if item["option_type"] == "CE"
    )
    assert ce["lot_size"] == 65
    assert ce["tick_size"] == 0.05
    assert ce["provider"] == "FYERS"
    assert ce["provider_timestamp"] == RECEIVED
    assert (
        ce["provider_timestamp_basis"]
        == "SYNCHRONOUS_FYERS_OPTIONCHAIN_RESPONSE"
    )


def test_fyers_certified_capture_fails_closed_when_one_side_missing():
    _, adapter = build(
        [
            {
                "symbol": "NSE:NIFTY26O0622450CE",
                "strike": 22450.0,
                "type": "CE",
                "ltp": 120.0,
                "bid": 119.5,
                "ask": 120.0,
                "oi": 1000,
                "volume": 5000,
                "expiry": "2026-10-06",
            }
        ]
    )

    result = adapter.capture_option_inputs(
        underlying="NIFTY",
        spot_price=22460.0,
        option_exchange="NFO",
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert result.blockers == ("FYERS_OPTION_CHAIN_INCOMPLETE",)
    assert result.metadata["ce_count"] == 1
    assert result.metadata["pe_count"] == 0


def test_fyers_certified_capture_rejects_provider_identity_mismatch():
    rows = [
        {
            "symbol": "NSE:WRONG26O0622450CE",
            "strike": 22450.0,
            "type": "CE",
            "ltp": 120.0,
            "expiry": "2026-10-06",
        },
        {
            "symbol": "NSE:WRONG26O0622450PE",
            "strike": 22450.0,
            "type": "PE",
            "ltp": 110.0,
            "expiry": "2026-10-06",
        },
    ]
    _, adapter = build(rows)

    result = adapter.capture_option_inputs(
        underlying="NIFTY",
        spot_price=22460.0,
        option_exchange="NFO",
        provider_timestamp=NOW,
        evaluated_at=NOW,
    )

    assert result.contracts == ()
    assert result.blockers == ("FYERS_OPTION_CHAIN_INCOMPLETE",)
    assert result.metadata["identity_resolution_failures"] == 2


def test_fyers_certified_capture_exposes_no_order_capability():
    _, adapter = build()
    assert adapter.data_only is True
    assert adapter.order_capability_allowed is False
    assert adapter.automatic_fallback_allowed is False
    assert not hasattr(adapter, "place_order")
    assert not hasattr(adapter, "submit_order")
