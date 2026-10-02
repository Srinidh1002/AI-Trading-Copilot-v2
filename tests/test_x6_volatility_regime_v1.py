"""X6-B3 descriptive IV, provenance, history, units and adversarial tests."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from test_x6_iv_greeks_v1 import MARKETS, captured, pricing

from services.x6.iv_greeks_v1 import analyze_iv_greeks_v1
from services.x6.volatility_regime_v1 import (
    analyze_volatility_regime_v1,
    make_x6_atm_history_point_v1,
)


def sample(market="NIFTY", *, pit=True, sigma=0.35, premiums=True, only_verified=True):
    x5, cap = captured(
        market=market, pit=pit, sigma=sigma, premiums=premiums, only_verified=only_verified
    )
    b2 = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    return x5, cap, b2


def analyze(x5, cap, b2, history=(), minimum=20):
    return analyze_volatility_regime_v1(
        capture=cap,
        source_x5=x5,
        iv_greeks=b2,
        history=history,
        history_minimum=minimum,
    )


def prior(market="NIFTY", *, amount=20, vols=None):
    x5, cap, b2 = sample(market)
    point = make_x6_atm_history_point_v1(capture=cap, source_x5=x5, iv_greeks=b2)
    if vols is None:
        vols = [0.20] * amount
    return tuple(
        replace(
            point,
            as_of=cap.context.as_of - timedelta(days=amount - n),
            session_id=f"session-history-{n}",
            capture_id=f"history-{n}",
            source_record_ids=(f"history-{n}-CE", f"history-{n}-PE"),
            source_x6_capture_sha256=f"{n + 10:064x}",
            source_iv_greeks_sha256=f"{n + 100:064x}",
            atm_iv_decimal=vols[n],
        )
        for n in range(amount)
    )


@pytest.mark.parametrize("market", MARKETS)
def test_current_atm_iv_skew_and_expected_move_all_markets(market):
    x5, cap, b2 = sample(market)
    result = analyze(x5, cap, b2)
    atm, skew, move, change, percentile = result.features
    assert result.status == "PARTIAL" and result.regime == "UNKNOWN"
    assert result.atm_strike == 100
    assert atm.value == pytest.approx(0.35, abs=1e-8)
    assert atm.unit == "DECIMAL_ANNUAL_VOLATILITY"
    assert skew.value == pytest.approx(0, abs=1e-8)
    assert skew.unit == "VOLATILITY_PERCENTAGE_POINTS_PUT_MINUS_CALL"
    assert move.value == pytest.approx(100 * 0.35 * cap.context.time_to_expiry_years() ** 0.5)
    assert move.unit == "UNDERLYING_PRICE_UNIT"
    assert move.warnings == ("APPROXIMATE_ONE_SIGMA_NOT_PRICE_BOUNDS",)
    assert change.status == percentile.status == "UNAVAILABLE"
    assert result.comparable_history_count == 0
    assert all(f.data_only is True and f.independent_vote is False for f in result.features)
    assert result.source_x6_capture_sha256 == cap.sha256()
    assert result.source_x5_capture_sha256 == x5.sha256()
    assert result.source_iv_greeks_sha256 == b2.sha256()


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("sigma", (0.12, 0.35, 0.8))
def test_scaled_sigma_scales_expected_move_and_atm(market, sigma):
    x5, cap, b2 = sample(market, sigma=sigma)
    result = analyze(x5, cap, b2)
    assert result.features[0].value == pytest.approx(sigma, abs=1e-8)
    assert result.features[2].value == pytest.approx(
        100 * sigma * cap.context.time_to_expiry_years() ** 0.5
    )


@pytest.mark.parametrize("market", MARKETS)
def test_history_point_provenance_and_contract(market):
    x5, cap, b2 = sample(market)
    p = make_x6_atm_history_point_v1(capture=cap, source_x5=x5, iv_greeks=b2)
    assert p.market == market
    assert p.as_of == cap.context.as_of
    assert p.atm_strike == 100
    assert p.atm_iv_decimal == pytest.approx(0.35)
    assert p.source_x6_capture_sha256 == cap.sha256()
    assert p.source_iv_greeks_sha256 == b2.sha256()
    assert p.sha256() == p.sha256()
    assert p.point_in_time_verified is True


@pytest.mark.parametrize("market", MARKETS)
def test_twenty_prior_sessions_yield_high_percentile(market):
    x5, cap, b2 = sample(market)
    history = prior(market)
    r = analyze(x5, cap, b2, history)
    assert r.status == "AVAILABLE"
    assert r.regime == "HIGH" and r.comparable_history_count == 20
    assert r.features[3].value == pytest.approx(15)
    assert r.features[4].value == pytest.approx(100)
    assert r.source_history_sha256 == tuple(p.sha256() for p in history)
    assert r.sha256() == r.sha256()


@pytest.mark.parametrize("market", MARKETS)
def test_prior_higher_iv_yields_low_percentile(market):
    x5, cap, b2 = sample(market)
    history = prior(market, vols=[0.70] * 20)
    r = analyze(x5, cap, b2, history)
    assert r.regime == "LOW"
    assert r.features[3].value == pytest.approx(-35)
    assert r.features[4].value == 0


@pytest.mark.parametrize("market", MARKETS)
def test_median_regime_is_descriptive_not_directional(market):
    x5, cap, b2 = sample(market)
    history = prior(market, vols=[0.2] * 10 + [0.5] * 10)
    r = analyze(x5, cap, b2, history)
    assert r.regime == "MIDDLE" and r.features[4].value == 50
    assert r.features[3].value == pytest.approx(-15)
    assert r.independent_vote is False


@pytest.mark.parametrize("n", (0, 1, 2, 5, 10, 19))
def test_insufficient_history_preserves_current_metrics(n):
    x5, cap, b2 = sample()
    h = prior(amount=n)
    r = analyze(x5, cap, b2, h)
    assert r.status == "PARTIAL" and r.regime == "UNKNOWN"
    assert r.features[0].value == pytest.approx(0.35)
    assert r.features[4].status == "UNAVAILABLE"
    assert r.features[3].status == ("AVAILABLE" if n else "UNAVAILABLE")


@pytest.mark.parametrize("minimum", (2, 5, 10, 20))
def test_configurable_explicit_history_minimum(minimum):
    x5, cap, b2 = sample()
    h = prior(amount=minimum)
    r = analyze(x5, cap, b2, h, minimum=minimum)
    assert r.regime == "HIGH" and r.history_minimum == minimum


@pytest.mark.parametrize("minimum", (-1, 0, 1, 10001, 2.5, "2", True))
def test_history_minimum_rejects_invalid_values(minimum):
    x5, cap, b2 = sample()
    with pytest.raises(ValueError):
        analyze(x5, cap, b2, minimum=minimum)


def test_mixed_expiry_excluded_and_no_false_percentile():
    x5, cap, b2 = sample()
    h = tuple(replace(p, option_expiry=date(2026, 10, 15)) for p in prior())
    r = analyze(x5, cap, b2, h)
    assert r.status == "PARTIAL" and r.regime == "UNKNOWN"
    assert r.comparable_history_count == 0
    assert r.source_history_sha256 == tuple(p.sha256() for p in h)
    assert "EXCLUDED_NONCOMPARABLE_EXPIRY_OR_ATM_STRIKE" in r.warnings


def test_strike_transition_excluded_from_comparison():
    x5, cap, b2 = sample()
    h = tuple(replace(p, atm_strike=110.0) for p in prior())
    r = analyze(x5, cap, b2, h)
    assert r.comparable_history_count == 0
    assert r.features[3].status == r.features[4].status == "UNAVAILABLE"


def test_mixed_compatible_and_incompatible_histories_disclosed():
    x5, cap, b2 = sample()
    h = prior()
    h = tuple(replace(h[0], atm_strike=110.0) for _ in range(1)) + h[1:]
    r = analyze(x5, cap, b2, h)
    assert r.comparable_history_count == 19 and r.status == "PARTIAL"
    assert r.features[3].status == "AVAILABLE"
    assert r.features[4].status == "UNAVAILABLE"
    assert "EXCLUDED_NONCOMPARABLE_EXPIRY_OR_ATM_STRIKE" in r.warnings


@pytest.mark.parametrize("market", MARKETS)
def test_retrospective_current_does_not_promote_history(market):
    x5, cap, b2 = sample(market, pit=False)
    r = analyze(x5, cap, b2, prior(market))
    assert r.status == "RETROSPECTIVE" and r.regime == "UNKNOWN"
    assert tuple(f.status for f in r.features) == (
        "RETROSPECTIVE",
        "RETROSPECTIVE",
        "RETROSPECTIVE",
        "UNAVAILABLE",
        "UNAVAILABLE",
    )
    with pytest.raises(ValueError):
        make_x6_atm_history_point_v1(capture=cap, source_x5=x5, iv_greeks=b2)


@pytest.mark.parametrize("market", MARKETS)
def test_unverified_premiums_cannot_supply_atm_history(market):
    x5, cap, b2 = sample(market, only_verified=False)
    r = analyze(x5, cap, b2)
    assert r.status == "UNAVAILABLE"
    assert r.regime == "UNKNOWN"
    assert all(f.status == "UNAVAILABLE" for f in r.features)
    assert r.atm_strike == 100
    with pytest.raises(ValueError):
        make_x6_atm_history_point_v1(capture=cap, source_x5=x5, iv_greeks=b2)


@pytest.mark.parametrize("market", MARKETS)
def test_missing_premiums_cannot_fabricate_iv(market):
    x5, cap, b2 = sample(market, premiums=False)
    r = analyze(x5, cap, b2)
    assert r.status == "UNAVAILABLE"
    assert all(f.value is None for f in r.features)


def test_one_unavailable_atm_side_blocks_all_current_metrics():
    x5, cap, _ = sample()
    cap = replace(
        cap,
        observations=tuple(
            replace(row, premium_verified=False) if row.option_type == "PE" else row
            for row in cap.observations
        ),
    )
    b2 = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    r = analyze(x5, cap, b2, prior())
    assert r.status == "UNAVAILABLE" and r.regime == "UNKNOWN"
    assert r.features[0].status == r.features[2].status == "UNAVAILABLE"
    assert r.features[3].status == r.features[4].status == "UNAVAILABLE"


@pytest.mark.parametrize(
    "field",
    ("source_x6_capture_sha256", "source_x5_capture_sha256", "source_validation_sha256", "status"),
)
def test_mismatched_b2_result_rejected_not_reinterpreted(field):
    x5, cap, b2 = sample()
    fake = replace(b2, **{field: "b" * 64 if field != "status" else "PARTIAL"})
    with pytest.raises(ValueError):
        analyze(x5, cap, fake)


@pytest.mark.parametrize("field", ("market", "model", "reference_unit"))
def test_mixed_market_history_rejected(field):
    x5, cap, b2 = sample()
    h = prior()
    options = {"market": "SENSEX", "model": "BLACK_76_FUTURES", "reference_unit": "INR_PER_BARREL"}
    with pytest.raises(ValueError):
        fake = replace(h[0], **{field: options[field]})
        analyze(x5, cap, b2, (fake,) + h[1:])


def test_out_of_order_history_rejected():
    x5, cap, b2 = sample()
    h = prior()
    with pytest.raises(ValueError):
        analyze(x5, cap, b2, tuple(reversed(h)))


def test_duplicate_session_and_capture_history_rejected():
    x5, cap, b2 = sample()
    h = prior()
    with pytest.raises(ValueError):
        analyze(x5, cap, b2, (h[0], replace(h[1], session_id=h[0].session_id)))
    with pytest.raises(ValueError):
        analyze(x5, cap, b2, (h[0], replace(h[1], capture_id=h[0].capture_id)))


def test_future_and_equal_time_history_rejected():
    x5, cap, b2 = sample()
    h = prior(amount=1)
    with pytest.raises(ValueError):
        analyze(x5, cap, b2, (replace(h[0], as_of=cap.context.as_of),))
    with pytest.raises(ValueError):
        analyze(x5, cap, b2, (replace(h[0], as_of=cap.context.as_of + timedelta(hours=1)),))


@pytest.mark.parametrize("type_name", (list, dict, set, str))
def test_history_must_be_immutable_tuple(type_name):
    x5, cap, b2 = sample()
    with pytest.raises(TypeError):
        analyze(x5, cap, b2, type_name())


@pytest.mark.parametrize(
    "field,value",
    (
        ("source_x6_capture_sha256", "invalid"),
        ("source_iv_greeks_sha256", "invalid"),
        ("atm_iv_decimal", 0),
        ("atm_iv_decimal", 6),
        ("atm_strike", 0),
        ("point_in_time_verified", False),
        ("live_execution_eligible", True),
        ("independent_vote", True),
        ("schema_version", "WRONG"),
    ),
)
def test_history_contract_rejects_invalid_identity_values_or_authority(field, value):
    p = prior(amount=1)[0]
    with pytest.raises(ValueError):
        replace(p, **{field: value})


@pytest.mark.parametrize(
    "field,value",
    (
        ("status", "AVAILABLE"),
        ("value", 0.0),
        ("unit", "PERCENT"),
        ("dependency_group", "FAKE"),
        ("independent_vote", True),
        ("live_execution_eligible", True),
    ),
)
def test_unavailable_feature_must_be_truly_unavailable(field, value):
    x5, cap, b2 = sample()
    feature = analyze(x5, cap, b2).features[4]
    with pytest.raises(ValueError):
        replace(feature, **{field: value})


@pytest.mark.parametrize(
    "field",
    (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "independent_vote",
    ),
)
def test_results_cannot_acquire_trading_authority(field):
    x5, cap, b2 = sample()
    r = analyze(x5, cap, b2)
    with pytest.raises(ValueError):
        replace(r, **{field: True})


def test_immutable_feature_result_and_history_contract():
    x5, cap, b2 = sample()
    r = analyze(x5, cap, b2)
    p = make_x6_atm_history_point_v1(capture=cap, source_x5=x5, iv_greeks=b2)
    for obj in (r, r.features[0], p):
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            obj.status = "ALTERED"


def test_source_hash_changes_if_input_history_changes():
    x5, cap, b2 = sample()
    h = prior()
    a = analyze(x5, cap, b2, h)
    b = analyze(x5, cap, b2, h)
    c = analyze(x5, cap, b2, h[:-1] + (replace(h[-1], atm_iv_decimal=0.27),))
    assert a.sha256() == b.sha256()
    assert a.sha256() != c.sha256()


def test_static_authority_scan_all_x6_sources():
    prohibited = {"place_order", "placeOrder", "execute_trade", "submit_order", "modify_order"}
    for path in Path("services/x6").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    not item.name.startswith(
                        ("fyers_apiv3", "SmartApi", "services.execution", "subprocess")
                    )
                    for item in node.names
                )
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("fyers_apiv3", "SmartApi", "services.execution", "subprocess")
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in prohibited


@pytest.mark.parametrize("market", MARKETS)
def test_true_put_call_atm_skew_is_percentage_points(market):
    x5, cap, _ = sample(market)
    put = next(r for r in cap.observations if r.option_type == "PE")
    premium = pricing(
        dict(
            model=cap.context.model,
            reference_price=cap.context.reference_price,
            strike=put.strike,
            years=cap.context.time_to_expiry_years(),
            rate=cap.context.annual_risk_free_rate,
            dividend_yield=cap.context.annual_dividend_yield,
            option_type="PE",
        ),
        0.5,
    )
    x5 = replace(
        x5,
        observations=tuple(
            replace(r, ltp=premium) if r.option_type == "PE" else r for r in x5.observations
        ),
    )
    cap = replace(
        cap,
        source_x5_capture_sha256=x5.sha256(),
        observations=tuple(
            replace(r, premium=premium) if r.option_type == "PE" else r for r in cap.observations
        ),
    )
    b2 = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    result = analyze(x5, cap, b2)
    assert result.features[0].value == pytest.approx(0.425, abs=1e-8)
    assert result.features[1].value == pytest.approx(15, abs=1e-8)
    assert result.regime == "UNKNOWN"


def test_nearest_incomplete_strike_does_not_fallback_to_distant_complete_pair():
    x5, cap, _ = sample()
    ce = next(row for row in x5.observations if row.option_type == "CE")
    opt = next(row for row in cap.observations if row.option_type == "CE")
    # The nearer 100.1 strike contains only a CE. The complete 100 pair may
    # remain available, but it must not silently replace the nearest strike.
    new_ce = replace(
        ce,
        strike=100.1,
        canonical_option_id="extra-CE-100.1",
        provider_symbol="NSE:NIFTY-100.1-CE",
        source_record_id="extra-CE-100.1",
    )
    new_opt = replace(
        opt, strike=100.1, canonical_option_id="extra-CE-100.1", source_record_id="extra-CE-100.1"
    )
    x5 = replace(x5, observations=x5.observations + (new_ce,), underlying_value=100.1)
    cap = replace(
        cap,
        source_x5_capture_sha256=x5.sha256(),
        context=replace(cap.context, reference_price=100.1),
        observations=cap.observations + (new_opt,),
    )
    b2 = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    result = analyze(x5, cap, b2)
    assert result.atm_strike == 100.1
    assert result.status == "UNAVAILABLE"
    assert result.blockers == ("NEAREST_STRIKE_PAIR_INCOMPLETE",)
    assert all(f.value is None for f in result.features)


def test_excluded_history_changes_result_hash_for_full_input_provenance():
    x5, cap, b2 = sample()
    h = tuple(replace(p, atm_strike=110) for p in prior())
    a = analyze(x5, cap, b2, h)
    h2 = h[:-1] + (replace(h[-1], atm_iv_decimal=0.6),)
    b = analyze(x5, cap, b2, h2)
    assert a.comparable_history_count == b.comparable_history_count == 0
    assert a.sha256() != b.sha256()
    assert a.source_history_sha256 != b.source_history_sha256


@pytest.mark.parametrize("status", ("AVAILABLE", "RETROSPECTIVE", "UNAVAILABLE"))
def test_partial_result_cannot_be_relabelled_as_other_status(status):
    x5, cap, b2 = sample()
    result = analyze(x5, cap, b2)
    assert result.status == "PARTIAL"
    with pytest.raises(ValueError):
        replace(result, status=status)
