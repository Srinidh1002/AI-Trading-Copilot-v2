"""X4 B2 offline multi-timeframe, contamination, replay and authority tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services.x4.contracts_v1 import X4BasisReferenceV1
from services.x4.fyers_adapter_v1 import adapt_fyers_futures_candles_v1
from services.x4.multi_timeframe_v1 import (
    X4MultiTimeframeResultV1,
    X4TimeframeEvidenceV1,
    compose_x4_multi_timeframe_v1,
)

NOW = datetime(2026, 10, 1, 10, 20, tzinfo=UTC)
UNITS = {
    "NIFTY": "INDEX_POINTS",
    "SENSEX": "INDEX_POINTS",
    "CRUDEOILM": "INR_PER_BARREL",
    "GOLDM": "INR_PER_10G",
    "NATGASMINI": "INR_PER_MMBTU",
}
SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600}


def _identity(market: str) -> SimpleNamespace:
    return SimpleNamespace(
        market_symbol=market,
        instrument_type="FUTURE",
        provider="FYERS",
        provider_symbol=f"FYERS:{market}:FUT",
        canonical_instrument_id=f"FYERS:{market}:20261030:FUT",
        expiry=date(2026, 10, 30),
        contract_metadata_status="VERIFIED",
        metadata_source="TEST_VERIFIED_MASTER",
        resolved_at=NOW - timedelta(days=1),
        data_only=True,
        live_execution_eligible=False,
    )


def _capture(
    market="NIFTY",
    tf="5m",
    *,
    now=NOW,
    prices=(100.0, 101.0, 102.0),
    oi=(1000, 1010, 1030),
    volume=(10, 20, 30),
    session="2026-10-01:S1",
    capture_id=None,
    **changes,
):
    delta = timedelta(seconds=SECONDS[tf])
    rows = []
    for i in range(3):
        end = now - delta * (2 - i)
        rows.append(
            {
                "provider": "FYERS",
                "provider_symbol": f"FYERS:{market}:FUT",
                "interval": tf,
                "timestamp": int((end - delta).timestamp()),
                "open": prices[i],
                "high": prices[i] + 1,
                "low": prices[i] - 1,
                "close": prices[i],
                "volume": volume[i],
                "open_interest": oi[i],
            }
        )
    args = dict(
        resolved=_identity(market),
        rows=rows,
        timeframe=tf,
        session_id=session,
        as_of=NOW,
        capture_id=capture_id or f"VERIFIED:{market}:{tf}",
        capture_verified=True,
        session_verified=True,
        timestamp_semantics_verified=True,
        price_unit=UNITS[market],
        price_unit_verified=True,
        volume_unit_verified=True,
        oi_unit_verified=True,
        oi_timestamp_verified=True,
    )
    args.update(changes)
    return adapt_fyers_futures_candles_v1(**args)


def _compose(market="NIFTY", *, captures=None, required=("5m", "15m"), **changes):
    captures = captures if captures is not None else {tf: _capture(market, tf) for tf in required}
    explicit_contract = changes.pop("contract", None)
    default_contract = (
        next(iter(captures.values())).contract if captures else _capture(market).contract
    )
    args = dict(
        contract=explicit_contract or default_contract,
        captures=captures,
        required_timeframes=required,
        max_age_seconds_by_timeframe={tf: SECONDS[tf] * 2 for tf in required},
        as_of=NOW,
    )
    args.update(changes)
    return compose_x4_multi_timeframe_v1(**args)


@pytest.mark.parametrize("market", tuple(UNITS))
def test_all_five_markets(market):
    result = _compose(market)
    assert result.market == market
    assert result.alignment == "CONSISTENT_UP"
    assert result.status == "PARTIAL"  # No verified spot/basis input.
    assert len(result.timeframe_results) == len(result.evidence) == 2
    assert all(frame.positioning_state == "LONG_BUILDUP" for frame in result.timeframe_results)
    assert result.data_only and not result.live_execution_eligible
    assert all(item.oi_change_verified and item.volume_change_verified for item in result.evidence)
    assert all(item.candle_vwap_estimate_available for item in result.evidence)


@pytest.mark.parametrize(
    "prices,oi,expected",
    (
        ((100, 101, 102), (1000, 1010, 1030), "CONSISTENT_UP"),
        ((100, 101, 102), (1030, 1010, 1000), "CONSISTENT_UP"),
        ((102, 101, 100), (1000, 1010, 1030), "CONSISTENT_DOWN"),
        ((102, 101, 100), (1030, 1010, 1000), "CONSISTENT_DOWN"),
        ((100, 100, 100), (1000, 1000, 1000), "FLAT"),
    ),
)
def test_directional_diagnostics_are_not_scores(prices, oi, expected):
    captures = {tf: _capture(tf=tf, prices=prices, oi=oi) for tf in ("5m", "15m")}
    result = _compose(captures=captures)
    assert result.alignment == expected
    assert not hasattr(result, "trade_action")
    assert not hasattr(result, "directional_score")


def test_mixed_positioning():
    captures = {
        "5m": _capture("NIFTY", "5m"),
        "15m": _capture("NIFTY", "15m", prices=(102, 101, 100)),
    }
    assert _compose(captures=captures).alignment == "MIXED"


def test_order_canonicalized_and_hash_deterministic():
    a = _capture("NIFTY", "5m")
    b = _capture("NIFTY", "15m")
    first = _compose(captures={"15m": b, "5m": a})
    second = _compose(captures={"5m": a, "15m": b})
    assert first.to_dict() == second.to_dict()
    assert first.sha256() == second.sha256()
    assert tuple(frame.timeframe for frame in first.timeframe_results) == ("5m", "15m")
    assert first.evidence[0].capture_id == a.capture_id


def test_verified_index_basis_makes_full_research_available():
    reference = X4BasisReferenceV1(
        market="NIFTY",
        benchmark_type="INDEX_SPOT",
        price=101.0,
        price_unit="INDEX_POINTS",
        source_id="TEST_SPOT_PROOF",
        observed_at=NOW,
        verified=True,
    )
    result = _compose(basis_reference=reference)
    assert result.status == "AVAILABLE"
    assert result.alignment == "CONSISTENT_UP"
    assert all("FUTURES_BASIS" in frame.available_feature_ids for frame in result.evidence)


def test_missing_frame_blocks_alignment_without_synthetic_frame():
    result = _compose(captures={"5m": _capture("NIFTY", "5m")})
    assert result.missing_timeframes == ("15m",)
    assert result.alignment == "INSUFFICIENT_DATA"
    assert result.status == "PARTIAL"
    assert len(result.timeframe_results) == 1
    assert "MISSING_TIMEFRAME:15m" in result.blockers


def test_all_missing_is_unavailable():
    contract = _capture().contract
    result = _compose(captures={}, contract=contract)
    assert result.status == "UNAVAILABLE"
    assert result.alignment == "INSUFFICIENT_DATA"
    assert len(result.missing_timeframes) == 2


def test_missing_oi_prevents_alignment():
    captures = {
        "5m": _capture("NIFTY", "5m", oi_unit_verified=False),
        "15m": _capture("NIFTY", "15m"),
    }
    result = _compose(captures=captures)
    assert result.alignment == "INSUFFICIENT_DATA"
    assert result.timeframe_results[0].positioning_state == "UNKNOWN"
    assert result.evidence[0].oi_change_verified is False
    assert "FUTURES_OI_CHANGE_PCT" in result.evidence[0].unavailable_feature_ids


@pytest.mark.parametrize("gate", ("oi_unit_verified", "oi_timestamp_verified"))
def test_unverified_oi_not_promoted(gate):
    result = _compose(captures={tf: _capture(tf=tf, **{gate: False}) for tf in ("5m", "15m")})
    assert result.alignment == "INSUFFICIENT_DATA"
    assert all(not frame.oi_change_verified for frame in result.evidence)


def test_unverified_volume_cannot_become_vwap_or_volume_evidence():
    result = _compose(
        captures={tf: _capture(tf=tf, volume_unit_verified=False) for tf in ("5m", "15m")}
    )
    assert result.alignment == "CONSISTENT_UP"  # OI + price are still verified.
    assert all(not frame.volume_change_verified for frame in result.evidence)
    assert all(not frame.candle_vwap_estimate_available for frame in result.evidence)
    assert result.status == "PARTIAL"


def test_stale_frame_blocks_alignment_and_marks_its_own_failure():
    captures = {
        "5m": _capture("NIFTY", "5m", now=NOW - timedelta(minutes=5)),
        "15m": _capture("NIFTY", "15m"),
    }
    result = _compose(captures=captures, max_age_seconds_by_timeframe={"5m": 90, "15m": 1800})
    assert result.alignment == "INSUFFICIENT_DATA"
    assert result.timeframe_results[0].status == "UNAVAILABLE"
    assert "5m:STALE_FUTURES_SAMPLE" in result.blockers


@pytest.mark.parametrize("tf", ("1m", "5m", "15m", "30m", "1h"))
def test_supported_timeframe_captures(tf):
    other = "15m" if tf != "15m" else "5m"
    required = (tf, other)
    result = _compose(
        captures={name: _capture(tf=name) for name in required},
        required=required,
    )
    assert result.alignment == "CONSISTENT_UP"
    assert tuple(result.required_timeframes) == required


def test_utc_and_ist_same_instant_is_accepted():
    ist = timezone(timedelta(hours=5, minutes=30))
    as_ist = NOW.astimezone(ist)
    result = _compose(as_of=as_ist)
    assert result.as_of == as_ist
    assert result.alignment == "CONSISTENT_UP"


@pytest.mark.parametrize(
    "changes",
    (
        {"required_timeframes": ("5m",)},
        {"required_timeframes": ("5m", "5m")},
        {"required_timeframes": ("5m", "1d")},
        {"max_age_seconds_by_timeframe": {"5m": 300}},
        {"max_age_seconds_by_timeframe": {"5m": 0, "15m": 900}},
        {"max_age_seconds_by_timeframe": {"5m": float("nan"), "15m": 900}},
        {"max_age_seconds_by_timeframe": {"5m": True, "15m": 900}},
        {"as_of": NOW.replace(tzinfo=None)},
        {"as_of": NOW + timedelta(seconds=1)},
    ),
)
def test_invalid_policy_and_as_of_rejected(changes):
    with pytest.raises(ValueError):
        _compose(**changes)


def test_extra_frame_rejected():
    captures = {tf: _capture(tf=tf) for tf in ("5m", "15m", "1m")}
    with pytest.raises(ValueError, match="Unexpected capture"):
        _compose(captures=captures)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda capture: replace(
            capture, contract=replace(capture.contract, provider_symbol="OTHER")
        ),
        lambda capture: replace(
            capture, contract=replace(capture.contract, expiry=date(2026, 11, 1))
        ),
        lambda capture: replace(
            capture, contract=replace(capture.contract, price_unit="INVALID_UNIT")
        ),
        lambda capture: replace(
            capture, contract=replace(capture.contract, metadata_source="OTHER")
        ),
        lambda capture: replace(capture, as_of=NOW + timedelta(minutes=1)),
        lambda capture: replace(
            capture, samples=tuple(replace(s, timeframe="1m") for s in capture.samples)
        ),
    ),
)
def test_identity_policy_and_capture_contamination_rejected(mutation):
    captures = {"5m": _capture("NIFTY", "5m"), "15m": mutation(_capture("NIFTY", "15m"))}
    with pytest.raises(ValueError):
        _compose(captures=captures)


@pytest.mark.parametrize("mutation", ({"data_only": False}, {"live_execution_eligible": True}))
def test_adapter_output_cannot_gain_authority(mutation):
    with pytest.raises(ValueError, match="data-only"):
        replace(_capture(), **mutation)


def test_reject_mixed_session():
    captures = {
        "5m": _capture("NIFTY", "5m"),
        "15m": _capture("NIFTY", "15m", session="2026-10-01:S2"),
    }
    with pytest.raises(ValueError, match="Mixed futures sessions"):
        _compose(captures=captures)


def test_reject_reused_capture_id():
    captures = {tf: _capture("NIFTY", tf, capture_id="ONE_CAPTURE_ID") for tf in ("5m", "15m")}
    with pytest.raises(ValueError, match="distinct"):
        _compose(captures=captures)


def test_unverified_metadata_yields_insufficient():
    captures = {
        tf: replace(
            _capture(tf=tf),
            contract=replace(_capture(tf=tf).contract, metadata_status="PROVISIONAL"),
        )
        for tf in ("5m", "15m")
    }
    result = _compose(captures=captures, contract=captures["5m"].contract)
    assert result.alignment == "INSUFFICIENT_DATA"
    assert result.status == "UNAVAILABLE"
    assert all(frame.status == "UNAVAILABLE" for frame in result.timeframe_results)


@pytest.mark.parametrize(
    "field",
    (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ),
)
def test_authority_never_activates(field):
    result = _compose()
    with pytest.raises(ValueError):
        replace(result, **{field: True})
    with pytest.raises(ValueError):
        replace(result.evidence[0], **{field: True})
    with pytest.raises(FrozenInstanceError):
        result.alignment = "CONSISTENT_DOWN"


def test_static_composer_has_no_order_capability():
    from pathlib import Path

    source = Path("services/x4/multi_timeframe_v1.py").read_text(encoding="utf-8")
    for prohibited in ("place_order(", "submit_order(", "certification_counter(", "requests."):
        assert prohibited not in source
    assert not hasattr(X4MultiTimeframeResultV1, "place_order")
    assert X4TimeframeEvidenceV1.__dataclass_params__.frozen is True
