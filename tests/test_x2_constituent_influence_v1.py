from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from services.x2.constituent_influence_v1 import (
    CONSTITUENT_INFLUENCE_SCHEMA_V1,
    ConstituentObservationV1,
    X2ConstituentError,
    compute_constituent_influence_v1,
)
from services.x2.constituent_universe_v1 import (
    WeightUnitV1,
    build_constituent_universe_v1,
)

OBSERVED_AT = datetime(2026, 9, 30, 10, 0, tzinfo=UTC)
OBS_DATE = date(2026, 9, 30)
EFF_DATE = date(2026, 9, 20)


def entry(cid, symbol, weight, exchange="NSE", sector="FINANCIALS"):
    return {
        "canonical_constituent_id": cid,
        "provider_symbol": symbol,
        "exchange": exchange,
        "weight": weight,
        "sector": sector,
    }


def universe(**overrides):
    defaults = dict(
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
        constituents=(
            entry("HDFCBANK", "HDFCBANK-EQ", 10.56),
            entry("ICICIBANK", "ICICIBANK-EQ", 8.32),
            entry("RELIANCE", "RELIANCE-EQ", 8.27),
            entry("INFY", "INFY-EQ", 3.61),
        ),
        expected_constituent_count=50,
        is_partial=True,
        missing_reason="only top weights retrieved",
    )
    defaults.update(overrides)
    if not defaults["is_partial"]:
        defaults["missing_reason"] = None
    return build_constituent_universe_v1(**defaults)


def obs(cid, ref, cur, *, at=None):
    return ConstituentObservationV1(
        canonical_constituent_id=cid,
        reference_price=ref,
        current_price=cur,
        observed_at=at or OBSERVED_AT,
    )


def test_valid_contributions_and_total():
    u = universe()
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
        "ICICIBANK": obs("ICICIBANK", 100.0, 99.0),
        "RELIANCE": obs("RELIANCE", 100.0, 100.5),
        "INFY": obs("INFY", 100.0, 100.0),
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
    )
    assert r.schema_version == CONSTITUENT_INFLUENCE_SCHEMA_V1
    assert len(r.contributions) == 4
    # HDFCBANK 10.56 * 0.01 = 0.1056
    by_id = {c.canonical_constituent_id: c for c in r.contributions}
    assert by_id["HDFCBANK"].contribution == pytest.approx(0.1056)
    assert by_id["ICICIBANK"].contribution == pytest.approx(-0.0832)
    assert by_id["RELIANCE"].contribution == pytest.approx(0.04135)
    assert by_id["INFY"].contribution == pytest.approx(0.0)
    assert r.total_contribution == pytest.approx(
        0.1056 - 0.0832 + 0.04135 + 0.0
    )


def test_contributions_are_ranked_by_contribution_desc():
    u = universe()
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
        "ICICIBANK": obs("ICICIBANK", 100.0, 99.0),
        "RELIANCE": obs("RELIANCE", 100.0, 100.5),
        "INFY": obs("INFY", 100.0, 100.0),
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
    )
    order = [c.canonical_constituent_id for c in r.contributions]
    assert order[0] == "HDFCBANK"
    assert order[1] == "RELIANCE"
    assert order[2] == "INFY"
    assert order[3] == "ICICIBANK"


def test_top_positive_and_negative():
    u = universe()
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
        "ICICIBANK": obs("ICICIBANK", 100.0, 97.0),
        "RELIANCE": obs("RELIANCE", 100.0, 100.5),
        "INFY": obs("INFY", 100.0, 100.0),
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
        top_k=1,
    )
    assert r.top_positive_contributors[0].canonical_constituent_id == (
        "HDFCBANK"
    )
    assert r.top_negative_contributors[0].canonical_constituent_id == (
        "ICICIBANK"
    )


def test_missing_observation_is_not_treated_as_zero():
    u = universe()
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
        # ICICIBANK, RELIANCE, INFY deliberately omitted
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
    )
    assert len(r.contributions) == 1
    assert len(r.missing_constituents) == 3
    reasons = {m.reason_code for m in r.missing_constituents}
    assert reasons == {"NO_OBSERVATION"}
    assert r.is_partial is True
    assert r.total_contribution == pytest.approx(0.1056)
    assert r.total_observed_weight == pytest.approx(10.56)


def test_stale_observation_is_not_admitted():
    u = universe()
    stale_at = OBSERVED_AT - timedelta(seconds=120)
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
        "ICICIBANK": obs(
            "ICICIBANK", 100.0, 99.0, at=stale_at
        ),
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
        stale_after_seconds=60.0,
    )
    assert len(r.contributions) == 1
    assert len(r.stale_constituents) == 1
    assert (
        r.stale_constituents[0].canonical_constituent_id == "ICICIBANK"
    )
    assert r.stale_constituents[0].reason_code == "STALE_OBSERVATION"


def test_future_observation_relative_to_calculated_at_fails():
    u = universe()
    future = OBSERVED_AT + timedelta(seconds=60)
    obsmap = {
        "HDFCBANK": obs(
            "HDFCBANK", 100.0, 101.0, at=future
        ),
    }
    with pytest.raises(X2ConstituentError):
        compute_constituent_influence_v1(
            universe=u,
            observations=obsmap,
            calculated_at=OBSERVED_AT,
        )


def test_concentration_top_k_share():
    u = universe()
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),   # +0.1056
        "ICICIBANK": obs("ICICIBANK", 100.0, 97.0),  # -0.2496
        "RELIANCE": obs("RELIANCE", 100.0, 100.5),   # +0.04135
        "INFY": obs("INFY", 100.0, 100.0),           # 0
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
        top_k=2,
    )
    abs_total = 0.1056 + 0.2496 + 0.04135
    expected_share = (0.2496 + 0.1056) / abs_total
    assert r.concentration_top_k_share == pytest.approx(expected_share)
    assert r.concentration_top_k == 2


def test_zero_range_returns_do_not_divide_by_zero():
    u = universe()
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 100.0),
        "ICICIBANK": obs("ICICIBANK", 100.0, 100.0),
        "RELIANCE": obs("RELIANCE", 100.0, 100.0),
        "INFY": obs("INFY", 100.0, 100.0),
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
    )
    assert r.concentration_top_k_share == 0.0
    assert r.total_contribution == pytest.approx(0.0)


def test_hash_is_deterministic_across_dict_order():
    u = universe()
    a = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
        "ICICIBANK": obs("ICICIBANK", 100.0, 99.0),
        "RELIANCE": obs("RELIANCE", 100.0, 100.5),
        "INFY": obs("INFY", 100.0, 100.0),
    }
    b = {
        "INFY": obs("INFY", 100.0, 100.0),
        "ICICIBANK": obs("ICICIBANK", 100.0, 99.0),
        "RELIANCE": obs("RELIANCE", 100.0, 100.5),
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
    }
    ra = compute_constituent_influence_v1(
        universe=u, observations=a, calculated_at=OBSERVED_AT
    )
    rb = compute_constituent_influence_v1(
        universe=u, observations=b, calculated_at=OBSERVED_AT
    )
    assert ra.result_sha256 == rb.result_sha256
    assert ra.canonical_json() == rb.canonical_json()


def test_no_index_point_attribution_field_is_exposed():
    u = universe()
    r = compute_constituent_influence_v1(
        universe=u,
        observations={"HDFCBANK": obs("HDFCBANK", 100.0, 101.0)},
        calculated_at=OBSERVED_AT,
    )
    payload = r.canonical_payload()
    forbidden = ("index_points", "index_point_contribution", "index_level")
    for name in forbidden:
        assert name not in payload


def test_rejects_bad_inputs():
    u = universe()
    with pytest.raises(X2ConstituentError):
        compute_constituent_influence_v1(
            universe=u,  # type: ignore[arg-type]
            observations=None,  # type: ignore[arg-type]
            calculated_at=OBSERVED_AT,
        )
    with pytest.raises(X2ConstituentError):
        compute_constituent_influence_v1(
            universe=u,
            observations={},
            calculated_at=OBSERVED_AT,
            top_k=0,
        )
    with pytest.raises(X2ConstituentError):
        compute_constituent_influence_v1(
            universe=u,
            observations={},
            calculated_at=OBSERVED_AT,
            stale_after_seconds=-1,
        )
    with pytest.raises(X2ConstituentError):
        compute_constituent_influence_v1(
            universe=u,
            observations={},
            calculated_at=datetime(2026, 9, 30, 10, 0),  # naive
        )


def test_observation_rejects_nonpositive_price():
    with pytest.raises(X2ConstituentError):
        ConstituentObservationV1(
            canonical_constituent_id="A",
            reference_price=0.0,
            current_price=100.0,
            observed_at=OBSERVED_AT,
        )
    with pytest.raises(X2ConstituentError):
        ConstituentObservationV1(
            canonical_constituent_id="A",
            reference_price=100.0,
            current_price=-1.0,
            observed_at=OBSERVED_AT,
        )


def test_coverage_ratio_reflects_expected_universe():
    u = universe(expected_constituent_count=4, is_partial=False)
    obsmap = {
        "HDFCBANK": obs("HDFCBANK", 100.0, 101.0),
        "ICICIBANK": obs("ICICIBANK", 100.0, 99.0),
    }
    r = compute_constituent_influence_v1(
        universe=u,
        observations=obsmap,
        calculated_at=OBSERVED_AT,
    )
    assert r.coverage_ratio == pytest.approx(0.5)
    assert r.is_partial is True  # missing observations make result partial
