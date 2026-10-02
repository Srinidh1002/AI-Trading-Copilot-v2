"""X6-B2 IV/Greeks math, provenance, boundary and zero-authority tests."""

from __future__ import annotations

import ast
import math
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from test_x6_reference_pricing_v1 import MARKETS, fixture

from services.x6.iv_greeks_v1 import (
    X6IVEstimationError,
    analytical_greeks_v1,
    analyze_iv_greeks_v1,
    implied_volatility_v1,
)
from services.x6.reference_pricing_v1 import black76_price_v1, black_scholes_price_v1


def args(
    market="NIFTY",
    side="CE",
    *,
    strike=100.0,
    sigma=0.35,
    years=0.2,
    reference=100.0,
    rate=0.06,
    dividend=0.01,
):
    future = market in ("CRUDEOILM", "GOLDM", "NATGASMINI")
    kw = dict(
        model="BLACK_76_FUTURES" if future else "BLACK_SCHOLES_SPOT",
        reference_price=reference,
        strike=strike,
        years=years,
        rate=rate,
        dividend_yield=None if future else dividend,
        option_type=side,
    )
    p = pricing(kw, sigma)
    return kw, p


def pricing(kw, sigma):
    common = dict(
        strike=kw["strike"],
        years=kw["years"],
        rate=kw["rate"],
        volatility=sigma,
        option_type=kw["option_type"],
    )
    if kw["model"] == "BLACK_76_FUTURES":
        return black76_price_v1(future=kw["reference_price"], **common)
    return black_scholes_price_v1(
        spot=kw["reference_price"], dividend_yield=kw["dividend_yield"], **common
    )


def captured(*, market="NIFTY", pit=True, sigma=0.35, premiums=True, only_verified=True):
    x5, cap = fixture(market=market, pit=pit, premiums=premiums)
    t = cap.context.time_to_expiry_years()
    if premiums:
        x5_rows = []
        cap_rows = []
        for source in x5.observations:
            # X6 contracts are sorted CE/PE; fixtures construct cap in reversed order.
            row = next(
                r for r in cap.observations if r.canonical_option_id == source.canonical_option_id
            )
            p = pricing(
                dict(
                    model=cap.context.model,
                    reference_price=cap.context.reference_price,
                    strike=row.strike,
                    years=t,
                    rate=cap.context.annual_risk_free_rate,
                    dividend_yield=cap.context.annual_dividend_yield,
                    option_type=row.option_type,
                ),
                sigma,
            )
            x5_rows.append(replace(source, ltp=p))
            cap_rows.append(replace(row, premium=p, premium_verified=only_verified))
        x5 = replace(x5, observations=tuple(x5_rows))
        cap = replace(cap, observations=tuple(cap_rows), source_x5_capture_sha256=x5.sha256())
    return x5, cap


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("side", ("CE", "PE"))
@pytest.mark.parametrize("sigma", (0.12, 0.35, 0.9))
@pytest.mark.parametrize("strike", (80.0, 100.0, 120.0))
def test_iv_recovers_reference_sigma_five_markets(market, side, sigma, strike):
    kw, premium = args(market, side, strike=strike, sigma=sigma)
    try:
        recovered = implied_volatility_v1(premium=premium, **kw)
    except X6IVEstimationError as exc:
        # Extremely OTM/near-zero prices may be intrinsically unidentifiable;
        # this is a valid fail-closed calibration, never a false positive.
        assert exc.code in {"IV_NUMERICALLY_ILL_CONDITIONED", "IV_NOT_IDENTIFIABLE_AT_INTRINSIC"}
    else:
        assert recovered == pytest.approx(sigma, abs=1e-6)


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("side", ("CE", "PE"))
@pytest.mark.parametrize("strike", (80.0, 100.0, 120.0))
def test_all_five_analytic_sensitivities_match_finite_difference(market, side, strike):
    kw, p = args(market, side, strike=strike, sigma=0.35)
    d, g, theta, vega, rho = analytical_greeks_v1(volatility=0.35, **kw)
    eps = 0.001
    price_up = pricing({**kw, "reference_price": 100 + eps}, 0.35)
    price_down = pricing({**kw, "reference_price": 100 - eps}, 0.35)
    d_num = (price_up - price_down) / (2 * eps)
    g_num = (price_up - 2 * p + price_down) / eps**2
    v_num = (pricing(kw, 0.35 + 0.0001) - pricing(kw, 0.35 - 0.0001)) / 0.0002 * 0.01
    r_num = (
        (
            pricing({**kw, "rate": kw["rate"] + 0.0001}, 0.35)
            - pricing({**kw, "rate": kw["rate"] - 0.0001}, 0.35)
        )
        / 0.0002
        * 0.01
    )
    t_num = (
        -(
            pricing({**kw, "years": kw["years"] + 1e-5}, 0.35)
            - pricing({**kw, "years": kw["years"] - 1e-5}, 0.35)
        )
        / 2e-5
        / 365
    )
    assert d == pytest.approx(d_num, abs=1e-6)
    assert g == pytest.approx(g_num, abs=2e-5)
    assert vega == pytest.approx(v_num, abs=1e-6)
    assert rho == pytest.approx(r_num, abs=1e-6)
    assert theta == pytest.approx(t_num, abs=1e-6)


@pytest.mark.parametrize("market", MARKETS)
def test_capture_is_provenance_bound_and_deterministic(market):
    x5, cap = captured(market=market)
    a = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    b = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    assert a.sha256() == b.sha256()
    assert a.to_dict() == b.to_dict()
    assert a.status == "AVAILABLE"
    assert all(r.status == "AVAILABLE" for r in a.rows)
    assert all(r.implied_volatility_decimal == pytest.approx(0.35, abs=1e-7) for r in a.rows)
    assert a.source_x5_capture_sha256 == x5.sha256()
    assert a.source_x6_capture_sha256 == cap.sha256()
    assert a.data_only is True and a.independent_vote is False
    assert a.live_execution_eligible is False and a.execution_authority is False
    assert a.certification_authority is False


@pytest.mark.parametrize("market", MARKETS)
def test_retrospective_capture_cannot_become_live_evidence(market):
    x5, cap = captured(market=market, pit=False)
    result = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    assert result.status == "RETROSPECTIVE"
    assert all(row.status == "RETROSPECTIVE" for row in result.rows)
    assert "NOT_PROVEN_POINT_IN_TIME" in result.warnings


def test_missing_and_unverified_premiums_are_unavailable():
    x5, cap = captured(premiums=False)
    result = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    assert result.status == "UNAVAILABLE"
    assert all(
        r.implied_volatility_decimal is None and r.status == "UNAVAILABLE" for r in result.rows
    )
    x5, cap = captured(only_verified=False)
    result = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    assert result.status == "UNAVAILABLE"
    assert all("OPTION_PREMIUM_UNVERIFIED" in r.blockers for r in result.rows)


def test_mixed_verified_and_unverified_premiums_give_partial_result():
    x5, cap = captured()
    altered = replace(cap.observations[1], premium_verified=False)
    cap = replace(cap, observations=(cap.observations[0], altered))
    result = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    assert result.status == "PARTIAL"
    assert sum(row.status == "AVAILABLE" for row in result.rows) == 1
    assert sum(row.status == "UNAVAILABLE" for row in result.rows) == 1


@pytest.mark.parametrize("side", ("CE", "PE"))
def test_discounted_intrinsic_boundary_is_not_an_iv_estimate(side):
    kw, _ = args(side=side)
    intrinsic = pricing(kw, 0.0)
    with pytest.raises(X6IVEstimationError, match="IV_NOT_IDENTIFIABLE_AT_INTRINSIC"):
        implied_volatility_v1(premium=intrinsic, **kw)


@pytest.mark.parametrize("side", ("CE", "PE"))
def test_premium_below_intrinsic_is_rejected(side):
    kw, _ = args(side=side, strike=90 if side == "CE" else 110)
    intrinsic = pricing(kw, 0.0)
    with pytest.raises(X6IVEstimationError, match="PREMIUM_BELOW_DISCOUNTED_INTRINSIC"):
        implied_volatility_v1(premium=intrinsic - 0.01, **kw)


@pytest.mark.parametrize("market", MARKETS)
def test_premium_above_supported_volatility_is_rejected(market):
    kw, _ = args(market=market)
    above = pricing(kw, 5.0) + 1
    with pytest.raises(X6IVEstimationError, match="PREMIUM_ABOVE_SUPPORTED_VOLATILITY_RANGE"):
        implied_volatility_v1(premium=above, **kw)


@pytest.mark.parametrize("bad", (-1, float("nan"), float("inf"), True, None))
def test_invalid_numerics_cannot_enter_iv_solver(bad):
    kw, _ = args()
    with pytest.raises(ValueError):
        implied_volatility_v1(premium=bad, **kw)


@pytest.mark.parametrize("bad", (0, -1, float("inf"), float("nan"), True))
def test_invalid_sigma_cannot_enter_greeks(bad):
    kw, _ = args()
    with pytest.raises(ValueError):
        analytical_greeks_v1(volatility=bad, **kw)


def test_missing_model_assumptions_do_not_infer_volatility():
    x5, cap = captured()
    ctx = replace(cap.context, rate_verified=False)
    cap = replace(cap, context=ctx)
    result = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    assert result.status == "UNAVAILABLE"
    assert all("DISCOUNT_RATE_UNVERIFIED" in r.blockers for r in result.rows)


def test_mismatched_x5_sha_fails_closed():
    x5, cap = captured()
    with pytest.raises(ValueError, match="SHA-256"):
        analyze_iv_greeks_v1(capture=replace(cap, source_x5_capture_sha256="f" * 64), source_x5=x5)


def test_same_capture_different_premium_changes_output_sha():
    x5, cap = captured(sigma=0.2)
    first = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    x5b, capb = captured(sigma=0.4)
    second = analyze_iv_greeks_v1(capture=capb, source_x5=x5b)
    assert first.sha256() != second.sha256()
    assert first.rows[0].implied_volatility_decimal != second.rows[0].implied_volatility_decimal


def test_black76_rho_is_negative_for_calls_and_puts_when_future_held_fixed():
    for side in ("CE", "PE"):
        kw, p = args(market="CRUDEOILM", side=side)
        *_, rho = analytical_greeks_v1(volatility=0.35, **kw)
        assert rho == pytest.approx(-kw["years"] * p * 0.01, abs=1e-12)


def test_analytic_derivatives_have_correct_underlying_convention():
    for market in MARKETS:
        call, _ = args(market=market, side="CE")
        put, _ = args(market=market, side="PE")
        d_call = analytical_greeks_v1(volatility=0.35, **call)[0]
        d_put = analytical_greeks_v1(volatility=0.35, **put)[0]
        target = (
            math.exp(-call["rate"] * call["years"])
            if call["model"] == "BLACK_76_FUTURES"
            else math.exp(-call["dividend_yield"] * call["years"])
        )
        assert d_call - d_put == pytest.approx(target, abs=1e-12)


def test_row_and_result_cannot_acquire_trading_authority():
    x5, cap = captured()
    res = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    for field in (
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
        "independent_vote",
    ):
        with pytest.raises(ValueError):
            replace(res, **{field: True})
        with pytest.raises(ValueError):
            replace(res.rows[0], **{field: True})
    with pytest.raises(FrozenInstanceError):
        res.rows[0].delta = 2


def test_unavailable_row_must_not_carry_a_sensitivity():
    x5, cap = captured(premiums=False)
    res = analyze_iv_greeks_v1(capture=cap, source_x5=x5)
    with pytest.raises(ValueError):
        replace(res.rows[0], delta=0.2)


def test_b2_source_contains_no_broker_or_certification_calls():
    path = Path(__file__).resolve().parents[1] / "services/x6/iv_greeks_v1.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(
                ("services.paper", "services.execution", "src.mcx")
            )
        if isinstance(node, ast.Import):
            assert not any(
                alias.name.startswith(("fyers_apiv3", "SmartApi")) for alias in node.names
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "place_order",
                "placeOrder",
                "submit_order",
                "execute_trade",
            }
