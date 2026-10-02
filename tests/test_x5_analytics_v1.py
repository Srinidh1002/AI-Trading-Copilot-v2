"""Offline X5 options analytics: no SDK, auth, broker, execution or PAPER state."""

from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest
from test_x5_chain_contracts_v1 import MARKETS, capture, observation

from services.x5.analytics_v1 import (
    X5AnalyticsResultV1,
    X5ResearchMetricV1,
    analyze_x5_chain_v1,
)
from services.x5.chain_validation_v1 import METRICS, validate_x5_chain_v1
from services.x5.contracts_v1 import X5ChainCaptureV1


def result(c=None):
    return analyze_x5_chain_v1(capture=c or capture(), max_age_seconds=60)


def metric(r, name):
    return next(x for x in r.metrics if x.metric_name == name)


def pair(
    strike,
    *,
    call_oi=20,
    put_oi=20,
    call_volume=10,
    put_volume=10,
    call_delta=0.5,
    put_delta=-0.5,
    call_iv=25.0,
    put_iv=25.0,
    call_change=-2,
    put_change=-2,
    baseline="SAME_BASELINE",
):
    return (
        replace(
            observation("NIFTY", "CE", strike, serial=str(int(strike))),
            open_interest=call_oi,
            volume=call_volume,
            implied_volatility=call_iv,
            delta=call_delta,
            change_in_open_interest=call_change,
            oi_change_baseline_id=baseline,
        ),
        replace(
            observation("NIFTY", "PE", strike, serial=str(int(strike))),
            open_interest=put_oi,
            volume=put_volume,
            implied_volatility=put_iv,
            delta=put_delta,
            change_in_open_interest=put_change,
            oi_change_baseline_id=baseline,
        ),
    )


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_all_five_markets_evaluate_without_trade_authority(market):
    r = result(capture(market))
    assert r.market == market
    assert r.status == "AVAILABLE"
    assert r.data_only and r.independent_vote is False
    assert not r.live_execution_eligible and not r.execution_authority
    assert not r.risk_authority and not r.position_authority
    assert not r.certification_authority
    assert len(r.metrics) == len(METRICS)


@pytest.mark.parametrize("name", METRICS)
def test_every_metric_has_canonical_identity_and_captured_window_scope(name):
    x = metric(result(), name)
    assert x.status == "AVAILABLE"
    assert x.scope == "CAPTURED_STRIKE_WINDOW"
    assert x.dependency_group and x.unit
    assert x.independent_vote is False and x.data_only
    assert x.execution_authority is False


@pytest.mark.parametrize("name", METRICS)
def test_each_metric_fails_closed_on_unverified_capture(name):
    c = capture(capture_verified=False, point_in_time_verified=False)
    x = metric(result(c), name)
    assert x.status == "UNAVAILABLE" and x.value is None and x.blockers
    assert result(c).status == "UNAVAILABLE"


@pytest.mark.parametrize("name", METRICS)
def test_each_metric_fails_closed_on_stale_observations(name):
    c = capture(
        observations=tuple(
            replace(x, observed_at=x.observed_at - timedelta(hours=1))
            for x in capture().observations
        )
    )
    x = metric(result(c), name)
    assert x.status == "UNAVAILABLE" and x.value is None


@pytest.mark.parametrize("name", METRICS)
def test_each_metric_never_votes_or_changes_execution_flags(name):
    x = metric(result(), name)
    for field in (
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ):
        with pytest.raises(ValueError):
            replace(x, **{field: True})


def test_default_values_and_source_hashes():
    c = capture()
    r = result(c)
    assert r.source_capture_sha256 == c.sha256()
    assert r.source_validation_sha256 == validate_x5_chain_v1(c, max_age_seconds=60).sha256()
    assert metric(r, "PCR_OI").value == 1
    assert metric(r, "PCR_VOLUME").value == 1
    assert metric(r, "MAX_PAIN").value == 100
    assert metric(r, "OI_CONCENTRATION").value == 1
    assert metric(r, "OI_BUILDUP").value == 0
    assert metric(r, "OI_SUPPORT_RESISTANCE").value == 0
    assert metric(r, "IV_SKEW").value == 0
    assert metric(r, "QUOTE_SPREAD").value == 2000
    assert metric(r, "GREEKS").value == 0.5


def test_pcr_is_captured_window_put_over_call():
    c = capture(observations=pair(100, call_oi=50, put_oi=125, call_volume=50, put_volume=75))
    r = result(c)
    assert metric(r, "PCR_OI").value == 2.5
    assert metric(r, "PCR_VOLUME").value == 1.5
    assert dict(metric(r, "PCR_OI").detail) == {"put_total": 125, "call_total": 50}


@pytest.mark.parametrize("field,which", [("open_interest", "PCR_OI"), ("volume", "PCR_VOLUME")])
def test_zero_call_denominator_remains_unavailable(field, which):
    rows = pair(100)
    c = capture(observations=(replace(rows[0], **{field: 0}), rows[1]))
    x = metric(result(c), which)
    assert x.status == "UNAVAILABLE" and x.value is None
    assert x.blockers == ("ZERO_CALL_DENOMINATOR",)


@pytest.mark.parametrize("field,which", [("open_interest", "PCR_OI"), ("volume", "PCR_VOLUME")])
def test_zero_put_total_is_a_valid_zero_ratio(field, which):
    rows = pair(100)
    c = capture(observations=(rows[0], replace(rows[1], **{field: 0})))
    x = metric(result(c), which)
    assert x.status == "AVAILABLE" and x.value == 0


@pytest.mark.parametrize(
    "field,which,flags",
    [
        ("open_interest", "PCR_OI", {"oi_unit_verified": False, "oi_change_verified": False}),
        ("volume", "PCR_VOLUME", {"volume_unit_verified": False}),
        ("implied_volatility", "IV_SKEW", {"iv_verified": False}),
        ("delta", "GREEKS", {"greeks_verified": False}),
    ],
)
def test_unverified_metric_input_never_used(field, which, flags):
    rows = pair(100)
    c = capture(observations=(replace(rows[0], **flags), rows[1]))
    x = metric(result(c), which)
    assert x.status == "UNAVAILABLE"


def test_zero_total_oi_blocks_pain_and_concentration():
    c = capture(observations=pair(100, call_oi=0, put_oi=0))
    assert metric(result(c), "MAX_PAIN").blockers == ("ZERO_TOTAL_OI",)
    assert metric(result(c), "OI_CONCENTRATION").blockers == ("ZERO_TOTAL_OI",)


def test_max_pain_canonical_intrinsic_settlement_payout():
    rows = (
        pair(90, call_oi=100, put_oi=5)
        + pair(100, call_oi=30, put_oi=30)
        + pair(110, call_oi=5, put_oi=100)
    )
    r = result(capture(observations=rows))
    x = metric(r, "MAX_PAIN")
    assert x.status == "AVAILABLE" and x.value == 100
    assert x.supporting_strikes == (90, 100, 110)
    assert dict(x.detail)["minimum_pain"] == 2000


def test_max_pain_tie_break_nearest_spot_then_lower():
    rows = pair(90, call_oi=10, put_oi=10) + pair(110, call_oi=10, put_oi=10)
    r = result(capture(observations=rows))
    assert metric(r, "MAX_PAIN").value == 90
    assert dict(metric(r, "MAX_PAIN").detail)["tied_strike_count"] == 2


def test_oi_concentration_uses_largest_combined_strike():
    rows = pair(90, call_oi=10, put_oi=30) + pair(100, call_oi=80, put_oi=20)
    x = metric(result(capture(observations=rows)), "OI_CONCENTRATION")
    assert x.value == pytest.approx(100 / 140)
    assert dict(x.detail)["top_strike"] == 100


def test_oi_concentration_tie_breaks_lower_strike():
    rows = pair(90, call_oi=10, put_oi=30) + pair(110, call_oi=20, put_oi=20)
    x = metric(result(capture(observations=rows)), "OI_CONCENTRATION")
    assert dict(x.detail)["top_strike"] == 90


def test_oi_buildup_uses_signed_change_not_oi_or_volume():
    c = capture(observations=pair(100, call_change=-20, put_change=10))
    x = metric(result(c), "OI_BUILDUP")
    assert x.value == 1
    assert dict(x.detail)["net_change_imbalance"] == 30


def test_oi_buildup_zero_gross_returns_observed_neutral_zero():
    c = capture(observations=pair(100, call_change=0, put_change=0))
    x = metric(result(c), "OI_BUILDUP")
    assert x.value == 0 and dict(x.detail)["gross_absolute_change"] == 0


def test_oi_buildup_warns_both_sides_unwinding():
    c = capture(observations=pair(100, call_change=-20, put_change=-5))
    assert metric(result(c), "OI_BUILDUP").warnings == ("BOTH_SIDES_UNWINDING",)


def test_oi_change_different_baseline_ids_rejected_by_b2():
    rows = pair(100)
    c = capture(observations=(rows[0], replace(rows[1], oi_change_baseline_id="OTHER_WINDOW")))
    x = metric(result(c), "OI_BUILDUP")
    assert x.status == "UNAVAILABLE" and x.blockers == ("OI_CHANGE_BASELINE_NOT_COMPARABLE",)


def test_support_resistance_strongest_verified_oi_each_side():
    rows = (
        pair(90, call_oi=1, put_oi=20)
        + pair(100, call_oi=5, put_oi=10)
        + pair(110, call_oi=25, put_oi=5)
    )
    x = metric(result(capture(observations=rows)), "OI_SUPPORT_RESISTANCE")
    assert x.value == pytest.approx(2000)
    assert dict(x.detail)["support_strike"] == 90
    assert dict(x.detail)["resistance_strike"] == 110


def test_support_resistance_requires_both_level_sides():
    c = capture(underlying_value=1, observations=pair(90))
    assert metric(result(c), "OI_SUPPORT_RESISTANCE").blockers == ("BOTH_LEVEL_SIDES_REQUIRED",)


def test_iv_skew_put_minus_call_percentage_points():
    rows = pair(100, call_iv=22.0, put_iv=30.0)
    assert metric(result(capture(observations=rows)), "IV_SKEW").value == 8


def test_iv_skew_decimal_iv_converts_only_verified_unit():
    rows = pair(100, call_iv=0.22, put_iv=0.30)
    c = capture(observations=tuple(replace(x, iv_unit="DECIMAL") for x in rows))
    assert metric(result(c), "IV_SKEW").value == pytest.approx(8)


def test_mixed_iv_units_block_skew():
    rows = pair(100)
    c = capture(
        observations=(rows[0], replace(rows[1], iv_unit="DECIMAL", implied_volatility=0.25))
    )
    assert metric(result(c), "IV_SKEW").status == "UNAVAILABLE"


def test_spread_uses_verified_bid_ask_midpoint_not_last():
    rows = pair(100)
    c = capture(
        observations=(
            replace(rows[0], bid_price=9, ask_price=11, ltp=1000),
            replace(rows[1], bid_price=9, ask_price=11, ltp=1),
        )
    )
    assert metric(result(c), "QUOTE_SPREAD").value == 2000


def test_zero_midpoint_blocks_spread_not_substitutes():
    rows = pair(100)
    c = capture(observations=(replace(rows[0], bid_price=0, ask_price=0), rows[1]))
    assert metric(result(c), "QUOTE_SPREAD").blockers == ("ZERO_QUOTE_MIDPOINT",)


def test_greeks_describe_shape_without_entry_recommendation():
    rows = pair(100, call_delta=0.6, put_delta=-0.4)
    x = metric(result(capture(observations=rows)), "GREEKS")
    assert x.value == pytest.approx(0.5)
    assert dict(x.detail)["avg_call_delta"] == 0.6
    assert dict(x.detail)["avg_put_delta"] == -0.4
    assert not hasattr(x, "trade_action")


def test_malformed_capture_argument_rejected():
    with pytest.raises(ValueError):
        analyze_x5_chain_v1(capture=None, max_age_seconds=60)


@pytest.mark.parametrize("max_age", [0, -1, float("inf"), float("nan"), True])
def test_invalid_age_rejected(max_age):
    with pytest.raises(ValueError):
        analyze_x5_chain_v1(capture=capture(), max_age_seconds=max_age)


def test_reordering_rows_cannot_change_output_hash():
    c = capture()
    r = result(c)
    reordered = capture(observations=tuple(reversed(c.observations)))
    assert r.sha256() == result(reordered).sha256()


def test_mutating_values_changes_capture_and_result_hashes():
    c = capture()
    changed = capture(
        observations=(replace(c.observations[0], open_interest=100), c.observations[1])
    )
    assert result(c).sha256() != result(changed).sha256()


def test_repeat_replay_is_deterministic():
    c = capture()
    assert result(c).to_dict() == result(c).to_dict()
    assert result(c).sha256() == result(c).sha256()


def test_retrospective_retrieval_never_promotes_metrics():
    c = capture(
        historical_retrieval=True,
        point_in_time_verified=False,
        captured_at=capture().captured_at + timedelta(hours=1),
    )
    r = result(c)
    assert r.status == "UNAVAILABLE"
    assert all(x.value is None for x in r.metrics)


def test_incomplete_pairs_block_all_metrics_without_extrapolation():
    c = capture(observations=(observation("NIFTY", "CE"),))
    r = result(c)
    assert r.status == "UNAVAILABLE"
    assert all(x.status == "UNAVAILABLE" for x in r.metrics)


def test_single_unverified_oi_blocks_correlated_oi_metrics():
    rows = pair(100)
    c = capture(
        observations=(replace(rows[0], oi_unit_verified=False, oi_change_verified=False), rows[1])
    )
    r = result(c)
    for name in ("PCR_OI", "MAX_PAIN", "OI_CONCENTRATION", "OI_BUILDUP", "OI_SUPPORT_RESISTANCE"):
        assert metric(r, name).status == "UNAVAILABLE"
    assert metric(r, "PCR_VOLUME").status == "AVAILABLE"
    assert r.status == "PARTIAL"


def test_oi_metrics_share_a_single_correlation_group():
    r = result()
    groups = {
        metric(r, name).dependency_group
        for name in (
            "PCR_OI",
            "MAX_PAIN",
            "OI_CONCENTRATION",
            "OI_BUILDUP",
            "OI_SUPPORT_RESISTANCE",
        )
    }
    assert groups == {"OPTION_OI_POSITIONING"}


def test_analytics_result_is_immutable():
    r = result()
    with pytest.raises(FrozenInstanceError):
        r.capture_id = "OTHER"


@pytest.mark.parametrize(
    "field",
    [
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_analytics_cannot_acquire_authority(field):
    with pytest.raises(ValueError):
        replace(result(), **{field: True})


@pytest.mark.parametrize("field", ["value", "unit", "scope", "status", "dependency_group"])
def test_metric_contract_rejects_invalid_core_fields(field):
    x = metric(result(), "PCR_OI")
    invalid = {
        "value": None,
        "unit": "FAKE",
        "scope": "EXCHANGE_WIDE",
        "status": "INVALID",
        "dependency_group": "UNRELATED",
    }[field]
    with pytest.raises(ValueError):
        replace(x, **{field: invalid})


def test_unavailable_metric_must_have_blocker():
    x = metric(result(), "PCR_OI")
    with pytest.raises(ValueError):
        replace(x, status="UNAVAILABLE", value=None, blockers=())


def test_result_must_include_exact_metric_manifest():
    r = result()
    with pytest.raises(ValueError):
        replace(r, metrics=r.metrics[:-1])


def test_no_data_only_override():
    x = metric(result(), "PCR_OI")
    with pytest.raises(ValueError):
        replace(x, data_only=False)
    with pytest.raises(ValueError):
        replace(result(), data_only=False)


def test_analytics_result_type_and_scope():
    r = result()
    assert isinstance(r, X5AnalyticsResultV1)
    assert isinstance(r.metrics[0], X5ResearchMetricV1)
    assert r.scope == "CAPTURED_STRIKE_WINDOW"
    assert set(r.to_dict()) >= {"metrics", "source_capture_sha256", "source_validation_sha256"}


def test_capture_type_does_not_enable_runtime_authority():
    c = capture()
    assert isinstance(c, X5ChainCaptureV1)
    assert not c.execution_authority and not c.risk_authority
