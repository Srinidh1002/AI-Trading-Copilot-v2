from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from services.x2.constituent_universe_v1 import (
    WeightUnitV1,
    X2ConstituentError,
    build_constituent_universe_v1,
)
from services.x2.weighted_breadth_v1 import (
    WEIGHTED_BREADTH_SCHEMA_V1,
    BreadthPolicyV1,
    ConstituentBreadthInputV1,
    compute_weighted_breadth_v1,
    to_market_breadth_snapshot_v1,
)

OBSERVED_AT = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
OBS_DATE = date(2026, 9, 30)
EFF_DATE = date(2026, 9, 20)


def entry(cid, symbol, weight, exchange="NSE", sector=None):
    return {
        "canonical_constituent_id": cid,
        "provider_symbol": symbol,
        "exchange": exchange,
        "weight": weight,
        "sector": sector,
    }


def universe(
    *,
    entries=None,
    expected=10,
    is_partial=False,
    missing_reason=None,
):
    if entries is None:
        entries = (
            entry("A", "A-EQ", 10.0),
            entry("B", "B-EQ", 9.0),
            entry("C", "C-EQ", 8.0),
            entry("D", "D-EQ", 7.0),
            entry("E", "E-EQ", 6.0),
        )
    entries = tuple(entries)
    if expected < len(entries):
        entries = entries[:expected]
    return build_constituent_universe_v1(
        universe_id="NIFTY_2026_09",
        universe_version="v1",
        index_symbol="NIFTY",
        provider="FYERS",
        weight_unit=WeightUnitV1.PERCENT,
        weight_effective_date=EFF_DATE,
        observation_date=OBS_DATE,
        observed_at=OBSERVED_AT,
        source_id="NSE_INDICES_CSV",
        source_label="NSE published weights",
        constituents=entries,
        expected_constituent_count=expected,
        is_partial=is_partial,
        missing_reason=missing_reason,
    )


def inp(
    cid,
    change_pct,
    *,
    above_vwap=None,
    above_ema20=None,
    above_ema50=None,
    at=None,
):
    return ConstituentBreadthInputV1(
        canonical_constituent_id=cid,
        change_pct=change_pct,
        observed_at=at or OBSERVED_AT,
        above_vwap=above_vwap,
        above_ema20=above_ema20,
        above_ema50=above_ema50,
    )


def test_counts_and_ratio():
    u = universe(expected=5)
    inputs = {
        "A": inp("A", 1.0),
        "B": inp("B", 0.5),
        "C": inp("C", -0.4),
        "D": inp("D", 0.0),  # unchanged within band
        "E": inp("E", -1.0),
    }
    r = compute_weighted_breadth_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT
    )
    assert r.advancing_count == 2
    assert r.declining_count == 2
    assert r.unchanged_count == 1
    assert r.advance_decline_ratio == pytest.approx(1.0)
    assert r.advance_decline_difference == 0
    assert r.eligible_count == 5
    assert r.evidence_status == "READY"


def test_weighted_exposure_uses_weights():
    u = universe(expected=5)
    inputs = {
        "A": inp("A", 1.0),   # weight 10 -> adv
        "B": inp("B", -1.0),  # weight 9 -> dec
        "C": inp("C", 1.0),   # weight 8 -> adv
        "D": inp("D", -1.0),  # weight 7 -> dec
        "E": inp("E", 0.0),   # unchanged
    }
    r = compute_weighted_breadth_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT
    )
    assert r.weighted_advancing_exposure == pytest.approx(18.0)
    assert r.weighted_declining_exposure == pytest.approx(16.0)
    assert r.weighted_advancing_pct == pytest.approx(
        100.0 * 18.0 / 34.0
    )


def test_missing_indicator_is_not_treated_as_below():
    u = universe(expected=3)
    inputs = {
        "A": inp("A", 1.0, above_vwap=True, above_ema20=True),
        "B": inp("B", 1.0, above_vwap=True, above_ema20=False),
        "C": inp("C", 1.0, above_vwap=None, above_ema20=None),
    }
    r = compute_weighted_breadth_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT
    )
    assert r.above_vwap_eligible_count == 2
    assert r.above_vwap_count == 2
    assert r.above_vwap_pct == pytest.approx(100.0)
    assert r.above_ema20_eligible_count == 2
    assert r.above_ema20_count == 1
    assert r.above_ema20_pct == pytest.approx(50.0)


def test_missing_observation_is_not_unchanged():
    u = universe(expected=3)
    inputs = {
        "A": inp("A", 1.0),
        # B omitted -> missing, not unchanged
    }
    r = compute_weighted_breadth_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT
    )
    assert r.missing_count == 2
    assert r.unchanged_count == 0
    assert r.eligible_count == 1


def test_stale_is_recorded_not_admitted():
    u = universe(expected=2)
    stale_at = OBSERVED_AT - timedelta(seconds=120)
    inputs = {
        "A": inp("A", 1.0),
        "B": inp("B", 1.0, at=stale_at),
    }
    r = compute_weighted_breadth_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        stale_after_seconds=60.0,
    )
    assert r.stale_count == 1
    assert r.eligible_count == 1


def test_no_declines_gives_none_ratio():
    u = universe(expected=2)
    inputs = {
        "A": inp("A", 1.0),
        "B": inp("B", 1.0),
    }
    r = compute_weighted_breadth_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT
    )
    assert r.declining_count == 0
    assert r.advance_decline_ratio is None


def test_below_min_coverage_is_partial():
    u = universe(expected=100)
    inputs = {
        "A": inp("A", 1.0),
    }
    r = compute_weighted_breadth_v1(
        universe=u,
        inputs=inputs,
        calculated_at=OBSERVED_AT,
        policy=BreadthPolicyV1(min_coverage_ratio=0.5),
    )
    assert r.evidence_status == "PARTIAL"
    assert r.is_partial is True


def test_zero_eligible_is_unavailable():
    u = universe(expected=5)
    r = compute_weighted_breadth_v1(
        universe=u, inputs={}, calculated_at=OBSERVED_AT
    )
    assert r.evidence_status == "UNAVAILABLE"
    assert r.eligible_count == 0


def test_hash_is_deterministic_across_input_order():
    u = universe(expected=5)
    a = {
        "A": inp("A", 1.0, above_vwap=True),
        "B": inp("B", -1.0, above_vwap=False),
        "C": inp("C", 0.0, above_vwap=None),
        "D": inp("D", 1.0),
        "E": inp("E", -1.0),
    }
    b = {
        "E": inp("E", -1.0),
        "D": inp("D", 1.0),
        "C": inp("C", 0.0, above_vwap=None),
        "B": inp("B", -1.0, above_vwap=False),
        "A": inp("A", 1.0, above_vwap=True),
    }
    ra = compute_weighted_breadth_v1(
        universe=u, inputs=a, calculated_at=OBSERVED_AT
    )
    rb = compute_weighted_breadth_v1(
        universe=u, inputs=b, calculated_at=OBSERVED_AT
    )
    assert ra.result_sha256 == rb.result_sha256


def test_handoff_to_market_breadth_snapshot():
    u = universe(expected=5)
    inputs = {
        "A": inp("A", 1.0),
        "B": inp("B", -1.0),
        "C": inp("C", 0.0),
        "D": inp("D", 1.0),
        "E": inp("E", -1.0),
    }
    r = compute_weighted_breadth_v1(
        universe=u, inputs=inputs, calculated_at=OBSERVED_AT
    )
    snap = to_market_breadth_snapshot_v1(
        result=r, snapshot_id="X2_HANDOFF_1"
    )
    assert snap.advance_count == r.advancing_count
    assert snap.decline_count == r.declining_count
    assert snap.unchanged_count == r.unchanged_count
    assert snap.total_count == r.eligible_count
    assert snap.underlying_symbol == "NIFTY"
    assert snap.exchange == "NSE"


def test_future_input_is_rejected():
    u = universe(expected=1)
    future = OBSERVED_AT + timedelta(seconds=60)
    with pytest.raises(X2ConstituentError):
        compute_weighted_breadth_v1(
            universe=u,
            inputs={"A": inp("A", 1.0, at=future)},
            calculated_at=OBSERVED_AT,
        )


def test_rejects_bad_inputs():
    u = universe(expected=1)
    with pytest.raises(X2ConstituentError):
        compute_weighted_breadth_v1(
            universe=None,  # type: ignore[arg-type]
            inputs={},
            calculated_at=OBSERVED_AT,
        )
    with pytest.raises(X2ConstituentError):
        compute_weighted_breadth_v1(
            universe=u,
            inputs=None,  # type: ignore[arg-type]
            calculated_at=OBSERVED_AT,
        )
    with pytest.raises(X2ConstituentError):
        compute_weighted_breadth_v1(
            universe=u,
            inputs={},
            calculated_at=datetime(2026, 9, 30, 10, 0),  # naive
        )
    with pytest.raises(X2ConstituentError):
        compute_weighted_breadth_v1(
            universe=u,
            inputs={},
            calculated_at=OBSERVED_AT,
            policy=None,  # type: ignore[arg-type]
        )


def test_policy_rejects_bad_thresholds():
    with pytest.raises(X2ConstituentError):
        BreadthPolicyV1(unchanged_band_pct=-1)
    with pytest.raises(X2ConstituentError):
        BreadthPolicyV1(min_coverage_ratio=2.0)
    with pytest.raises(X2ConstituentError):
        BreadthPolicyV1(
            bullish_advance_decline_ratio=1.0,
            bearish_advance_decline_ratio=1.0,
        )


def test_result_schema_version():
    u = universe(expected=1)
    r = compute_weighted_breadth_v1(
        universe=u,
        inputs={"A": inp("A", 1.0)},
        calculated_at=OBSERVED_AT,
    )
    assert r.schema_version == WEIGHTED_BREADTH_SCHEMA_V1
