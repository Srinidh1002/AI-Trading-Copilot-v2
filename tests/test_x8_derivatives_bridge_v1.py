"""B3 typed derivatives bridges, point-in-time and provenance cases."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_x6_contracts_v1 import NOW, case

from services.x4.contracts_v1 import X4ResultV1
from services.x6.input_validation_v1 import validate_x6_input_v1
from services.x7.contracts_v1 import MARKETS
from services.x8.derivatives_bridge_v1 import (
    bind_x4_futures_to_x8_v1,
    bind_x6_volatility_to_x8_v1,
)


def x4(market="NIFTY", status="AVAILABLE"):
    return X4ResultV1(
        market=market,
        instrument_id=market + "_FUT",
        session_id="session-1",
        timeframe="5m",
        as_of=NOW,
        features=(),
        positioning_state="UNKNOWN",
        status=status,
        blockers=(),
    )


def x4_ref(market="NIFTY", source=None, **changes):
    source = source or x4(market)
    args = dict(
        market=market,
        session_id="session-1",
        capture_id="capture-1",
        as_of=NOW + timedelta(seconds=2),
        result=source,
        expected_result_sha256=source.sha256(),
        result_available_at=NOW + timedelta(seconds=1),
        max_age_seconds=60,
    )
    args.update(changes)
    return bind_x4_futures_to_x8_v1(**args)


def x6_ref(market="NIFTY", point_in_time=True, **changes):
    x5, cap = case(market, point_in_time=point_in_time)
    validation = validate_x6_input_v1(capture=cap, source_x5=x5)
    args = dict(
        market=market,
        session_id=x5.session_id,
        capture_id=x5.capture_id,
        as_of=NOW + timedelta(seconds=2),
        capture=cap,
        source_x5=x5,
        validation=validation,
        expected_capture_sha256=cap.sha256(),
        expected_x5_sha256=x5.sha256(),
        expected_validation_sha256=validation.sha256(),
        result_available_at=NOW + timedelta(seconds=1),
        max_age_seconds=60,
    )
    args.update(changes)
    return bind_x6_volatility_to_x8_v1(**args)


@pytest.mark.parametrize("market", MARKETS)
def test_x4_result_cannot_become_verified_pit_from_aggregate(market):
    row = x4_ref(market)
    assert row.family == "FUTURES" and row.state == "UNVERIFIED"
    assert row.point_in_time_verified is False
    assert not row.execution_authority and not row.independent_vote


@pytest.mark.parametrize("market", MARKETS)
def test_x4_unavailable_remains_unavailable(market):
    assert x4_ref(market, source=x4(market, "UNAVAILABLE")).state == "UNAVAILABLE"


@pytest.mark.parametrize("market", MARKETS)
def test_x6_exact_x5_provenance_available_across_markets(market):
    row = x6_ref(market)
    assert row.family == "VOLATILITY" and row.state == "AVAILABLE"
    assert row.point_in_time_verified and not row.risk_authority


@pytest.mark.parametrize("market", MARKETS)
def test_x6_retrospective_is_never_available(market):
    row = x6_ref(
        market,
        point_in_time=False,
        as_of=NOW + timedelta(seconds=10),
        result_available_at=NOW + timedelta(seconds=6),
    )
    assert row.state == "UNVERIFIED"
    assert not row.point_in_time_verified


@pytest.mark.parametrize("market", MARKETS)
def test_x4_hash_tampering_rejected(market):
    with pytest.raises(ValueError, match="hash"):
        x4_ref(market, expected_result_sha256="f" * 64)


@pytest.mark.parametrize("market", MARKETS)
def test_x6_hash_tampering_rejected(market):
    with pytest.raises(ValueError, match="hash"):
        x6_ref(market, expected_validation_sha256="f" * 64)


@pytest.mark.parametrize("market", MARKETS)
def test_x6_future_availability_rejected(market):
    with pytest.raises(ValueError, match="future"):
        x6_ref(market, result_available_at=NOW + timedelta(seconds=10))


@pytest.mark.parametrize("market", MARKETS)
def test_x4_age_limit_marked_stale(market):
    assert x4_ref(market, as_of=NOW + timedelta(seconds=90)).state == "STALE"


def test_x4_wrong_market_fails_closed():
    with pytest.raises(ValueError, match="mismatch"):
        x4_ref("SENSEX", source=x4("NIFTY"))


def test_x6_wrong_market_fails_closed():
    x5, capture = case("NIFTY")
    validation = validate_x6_input_v1(capture=capture, source_x5=x5)
    with pytest.raises(ValueError, match="mismatch"):
        bind_x6_volatility_to_x8_v1(
            market="SENSEX",
            session_id=x5.session_id,
            capture_id=x5.capture_id,
            as_of=NOW + timedelta(seconds=2),
            capture=capture,
            source_x5=x5,
            validation=validation,
            expected_capture_sha256=capture.sha256(),
            expected_x5_sha256=x5.sha256(),
            expected_validation_sha256=validation.sha256(),
            result_available_at=NOW + timedelta(seconds=1),
            max_age_seconds=60,
        )


def test_tampered_x6_validation_even_with_claimed_matching_hash_fails_closed():
    x5, cap = case()
    valid = validate_x6_input_v1(capture=cap, source_x5=x5)
    bad = replace(valid, status="PARTIAL")
    with pytest.raises(ValueError, match="reproduced"):
        x6_ref(capture=cap, source_x5=x5, validation=bad, expected_validation_sha256=bad.sha256())


@pytest.mark.parametrize("bad", (0, -1, float("nan"), True, None))
def test_bad_freshness_budget_rejected(bad):
    with pytest.raises(ValueError):
        x4_ref(max_age_seconds=bad)


def test_x6_reference_cannot_acquire_authority():
    with pytest.raises(ValueError):
        replace(x6_ref(), execution_authority=True)
