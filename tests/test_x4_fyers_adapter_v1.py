"""No credentials, SDK, network, execution or PAPER state; offline adapter tests."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest

from services.x4.futures_engine_v1 import analyze_futures_v1
from services.x4.fyers_adapter_v1 import adapt_fyers_futures_candles_v1

NOW = datetime(2026, 10, 1, 10, 20, tzinfo=UTC)
MARKETS = {
    "NIFTY": "INDEX_POINTS",
    "SENSEX": "INDEX_POINTS",
    "CRUDEOILM": "INR_PER_BARREL",
    "GOLDM": "INR_PER_10G",
    "NATGASMINI": "INR_PER_MMBTU",
}


def identity(market="NIFTY"):
    return SimpleNamespace(
        market_symbol=market,
        provider="FYERS",
        instrument_type="FUTURE",
        provider_symbol=f"FYERS:{market}:FUT",
        canonical_instrument_id=f"FYERS:{market}:20261030:FUT",
        expiry=date(2026, 10, 30),
        contract_metadata_status="VERIFIED",
        metadata_source="VERIFIED_TEST_MASTER",
        resolved_at=NOW - timedelta(days=2),
        data_only=True,
        live_execution_eligible=False,
    )


def rows(market="NIFTY"):
    return [
        {
            "provider": "FYERS",
            "provider_symbol": f"FYERS:{market}:FUT",
            "interval": "5m",
            "timestamp": int((NOW - timedelta(minutes=15 - i * 5)).timestamp()),
            "open": 100.0 + i,
            "high": 101.0 + i,
            "low": 99.0 + i,
            "close": 100.0 + i,
            "volume": 10 + i,
            "open_interest": 1000 + i * 10,
        }
        for i in range(3)
    ]


def adapt(market="NIFTY", **changes):
    values = dict(
        resolved=identity(market),
        rows=rows(market),
        timeframe="5m",
        session_id="2026-10-01:VERIFIED_SESSION",
        as_of=NOW,
        capture_id="X1_VERIFIED_CAPTURE_TEST",
        capture_verified=True,
        session_verified=True,
        timestamp_semantics_verified=True,
        price_unit=MARKETS[market],
        price_unit_verified=True,
        volume_unit_verified=True,
        oi_unit_verified=True,
        oi_timestamp_verified=True,
    )
    values.update(changes)
    return adapt_fyers_futures_candles_v1(**values)


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_five_markets_and_exact_identity(market):
    result = adapt(market)
    assert result.contract.market == market
    assert result.contract.canonical_instrument_id == identity(market).canonical_instrument_id
    assert all(s.contract_id == result.contract.canonical_instrument_id for s in result.samples)
    assert result.data_only and result.live_execution_eligible is False
    assert result.samples[-1].observed_at == NOW
    assert all(s.oi_verified and s.volume_verified and s.is_closed for s in result.samples)


def test_end_to_end_existing_pure_engine():
    result = adapt()
    analyzed = analyze_futures_v1(
        contract=result.contract,
        samples=result.samples,
        as_of=result.as_of,
        max_age_seconds=360,
    )
    assert analyzed.positioning_state == "LONG_BUILDUP"
    assert analyzed.data_only and not analyzed.live_execution_eligible


@pytest.mark.parametrize(
    "gate",
    (
        "capture_verified",
        "session_verified",
        "timestamp_semantics_verified",
        "price_unit_verified",
    ),
)
def test_required_proof_gate_fails_closed(gate):
    with pytest.raises(ValueError):
        adapt(**{gate: False})


@pytest.mark.parametrize(
    "gate", ("volume_unit_verified", "oi_unit_verified", "oi_timestamp_verified")
)
def test_unverified_metric_is_not_promoted(gate):
    result = adapt(**{gate: False})
    if gate == "volume_unit_verified":
        assert not any(s.volume_verified for s in result.samples)
    else:
        assert not any(s.oi_verified for s in result.samples)


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_wrong_price_unit_is_rejected(market):
    with pytest.raises(ValueError, match="price unit"):
        adapt(market, price_unit="INR_PER_QUOTE_UNIT")


@pytest.mark.parametrize(
    "replacement",
    (
        {"provider_symbol": "FYERS:OTHER:FUT"},
        {"provider": "ANGEL_SMARTAPI"},
        {"instrument_type": "OPTION"},
        {"data_only": False},
        {"live_execution_eligible": True},
        {"metadata_source": None},
        {"resolved_at": NOW + timedelta(minutes=1)},
        {"contract_metadata_status": "INVALID"},
    ),
)
def test_bad_identity_rejected(replacement):
    obj = identity()
    for key, value in replacement.items():
        setattr(obj, key, value)
    with pytest.raises(ValueError):
        adapt(resolved=obj)


@pytest.mark.parametrize(
    "replacement",
    (
        {"provider_symbol": "OTHER"},
        {"provider": "ANGEL_SMARTAPI"},
        {"interval": "15m"},
        {"timestamp": "2026-10-01T10:00:00Z"},
        {"timestamp": 1720000000000},
        {"close": 0},
        {"high": 98},
        {"open": 200},
        {"volume": -1},
        {"open_interest": 0},
    ),
)
def test_bad_candle_rejected(replacement):
    r = rows()
    r[-1] = {**r[-1], **replacement}
    with pytest.raises(ValueError):
        adapt(rows=r)


def test_unclosed_bar_rejected():
    r = rows()
    r[-1]["timestamp"] = int((NOW - timedelta(minutes=2)).timestamp())
    with pytest.raises(ValueError, match="Unclosed"):
        adapt(rows=r)


def test_duplicate_and_reordered_bar_rejected():
    r = rows()
    r[-1]["timestamp"] = r[-2]["timestamp"]
    with pytest.raises(ValueError, match="Overlapping"):
        adapt(rows=r)


def test_unavailable_oi_retains_price_evidence_only():
    r = rows()
    for record in r:
        record.pop("open_interest")
    adapted = adapt(rows=r)
    analyzed = analyze_futures_v1(
        contract=adapted.contract,
        samples=adapted.samples,
        as_of=NOW,
        max_age_seconds=360,
    )
    assert analyzed.positioning_state == "UNKNOWN"
    assert any(
        feature.feature_id == "FUTURES_PRICE_CHANGE_PCT" and feature.status == "AVAILABLE"
        for feature in analyzed.features
    )
    assert any(
        feature.feature_id == "FUTURES_OI_CHANGE_PCT" and feature.status == "UNAVAILABLE"
        for feature in analyzed.features
    )


def test_provisional_contract_fails_closed_in_engine():
    obj = identity()
    obj.contract_metadata_status = "PROVISIONAL"
    adapted = adapt(resolved=obj)
    analyzed = analyze_futures_v1(
        contract=adapted.contract,
        samples=adapted.samples,
        as_of=NOW,
        max_age_seconds=360,
    )
    assert analyzed.status == "UNAVAILABLE" and not analyzed.features


def test_no_synthetic_volume_or_oi():
    r = rows()
    for record in r:
        record.pop("volume")
        record.pop("open_interest")
    adapted = adapt(rows=r)
    assert all(s.volume is None and s.open_interest is None for s in adapted.samples)
    assert all(not s.volume_verified and not s.oi_verified for s in adapted.samples)


def test_bad_boolean_verification_gate():
    with pytest.raises(ValueError, match="exact booleans"):
        adapt(capture_verified=1)


def test_unsupported_daily_bar_semantics_fail_closed():
    with pytest.raises(ValueError, match="timeframe"):
        adapt(timeframe="1d")


def test_result_contract_immutable():
    with pytest.raises((AttributeError, TypeError)):
        result = adapt()
        result.contract = replace(result.contract, market="SENSEX")
