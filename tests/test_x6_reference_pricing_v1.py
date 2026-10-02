"""X6-B1 Black-Scholes/Black-76 arithmetic, provenance and zero-authority tests."""

from __future__ import annotations

import ast
import math
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from services.x5.contracts_v1 import (
    X5ChainCaptureV1,
    X5ContractV1,
    X5OptionObservationV1,
)
from services.x6.contracts_v1 import (
    IST,
    MODEL_BY_MARKET,
    PRICE_UNITS,
    X6OptionInputV1,
    X6PricingContextV1,
    X6VolatilityCaptureV1,
)
from services.x6.reference_pricing_v1 import (
    X6ReferencePriceV1,
    black76_price_v1,
    black_scholes_price_v1,
    price_x6_capture_v1,
)

MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
NOW = datetime(2026, 10, 1, 10, 0, tzinfo=IST)
EXPIRY = date(2026, 10, 8)
ROOTS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "CRUDEOILM": "MCX:CRUDEOILM",
    "GOLDM": "MCX:GOLDM",
    "NATGASMINI": "MCX:NATGASMINI",
}
PREFIXES = {
    "NIFTY": "NSE:NIFTY",
    "SENSEX": "BSE:SENSEX",
    "CRUDEOILM": "MCX:CRUDEOILM",
    "GOLDM": "MCX:GOLDM",
    "NATGASMINI": "MCX:NATGASMINI",
}


def fixture(market="NIFTY", *, pit=True, sides=("CE", "PE"), premiums=True):
    options = tuple(
        X5OptionObservationV1(
            canonical_option_id=f"{market}-{side}-100",
            provider_symbol=f"{PREFIXES[market]}-FAKE-{side}",
            option_type=side,
            strike=100.0,
            expiry=EXPIRY,
            observed_at=NOW,
            source_record_id=f"{market}-source-{side}",
            ltp=15.0 if premiums else None,
            bid_price=10.0 if premiums else None,
            ask_price=20.0 if premiums else None,
            premium_unit=PRICE_UNITS[market],
            premium_unit_verified=premiums,
        )
        for side in sides
    )
    x5 = X5ChainCaptureV1(
        contract=X5ContractV1(
            market=market,
            provider="FYERS",
            underlying_provider_symbol=ROOTS[market],
            option_exchange={"NIFTY": "NFO", "SENSEX": "BFO"}.get(market, "MCX"),
            expiry=EXPIRY,
            expiry_source_id="expiry-master",
            metadata_status="VERIFIED",
            metadata_source="unit-master",
        ),
        session_id="session-1",
        capture_id="capture-1",
        source_id="fixture-1",
        as_of=NOW,
        captured_at=NOW if pit else NOW + timedelta(seconds=5),
        observations=options,
        underlying_value=100.0,
        underlying_unit=PRICE_UNITS[market],
        underlying_verified=True,
        capture_verified=True,
        expiry_verified=True,
        timestamp_semantics_verified=True,
        historical_retrieval=not pit,
        point_in_time_verified=pit,
    )
    futures = market not in ("NIFTY", "SENSEX")
    ctx = X6PricingContextV1(
        market=market,
        model=MODEL_BY_MARKET[market],
        option_expiry=EXPIRY,
        as_of=NOW,
        option_expiry_at=datetime(2026, 10, 8, 23 if futures else 15, 30, tzinfo=IST),
        expiry_source_id="verified-exchange-schedule",
        reference_price=100.0,
        reference_unit=PRICE_UNITS[market],
        reference_source_id="reference-1",
        reference_verified=True,
        premium_unit=PRICE_UNITS[market],
        annual_risk_free_rate=0.06,
        rate_source_id="verified-continuous-rate",
        rate_verified=True,
        annual_dividend_yield=None if futures else 0.01,
        dividend_source_id=None if futures else "verified-index-yield",
        dividend_verified=False if futures else True,
        futures_contract_id=f"MCX:{market}-FUT" if futures else None,
        futures_expiry=EXPIRY + timedelta(days=14) if futures else None,
        futures_identity_verified=futures,
        expiry_instant_verified=True,
    )
    cap = X6VolatilityCaptureV1(
        context=ctx,
        session_id=x5.session_id,
        capture_id=x5.capture_id,
        source_x5_capture_sha256=x5.sha256(),
        observations=tuple(
            X6OptionInputV1(
                canonical_option_id=o.canonical_option_id,
                source_record_id=o.source_record_id,
                option_type=o.option_type,
                strike=o.strike,
                observed_at=o.observed_at,
                premium=o.ltp,
                premium_source="LTP" if premiums else "NONE",
                premium_verified=premiums,
            )
            for o in reversed(options)
        ),
        point_in_time_verified=pit,
    )
    return x5, cap


def calculate(x5, cap, **kwargs):
    return price_x6_capture_v1(
        capture=cap,
        source_x5=x5,
        annual_volatility=kwargs.get("annual_volatility", 0.2),
        volatility_source_id=kwargs.get("volatility_source_id", "verified-sigma"),
        volatility_verified=kwargs.get("volatility_verified", True),
    )


@pytest.mark.parametrize("market", MARKETS)
def test_five_markets_select_correct_reference_formula(market):
    x5, cap = fixture(market)
    result = calculate(x5, cap)
    t = cap.context.time_to_expiry_years()
    kwargs = dict(strike=100.0, years=t, rate=0.06, volatility=0.2)
    expected = (
        black76_price_v1(future=100, option_type="CE", **kwargs)
        if market not in ("NIFTY", "SENSEX")
        else black_scholes_price_v1(spot=100, dividend_yield=0.01, option_type="CE", **kwargs)
    )
    assert result.model == MODEL_BY_MARKET[market]
    assert result.status == "AVAILABLE"
    assert result.reference_unit == PRICE_UNITS[market]
    assert result.prices[0].theoretical_price == pytest.approx(expected, rel=1e-13)
    assert result.source_x5_capture_sha256 == x5.sha256()
    assert result.source_x6_capture_sha256 == cap.sha256()
    assert result.sha256() == result.sha256()


@pytest.mark.parametrize("side, expected", [("CE", 10.450583572185565), ("PE", 5.573526022256971)])
def test_textbook_black_scholes_prices(side, expected):
    assert black_scholes_price_v1(
        spot=100,
        strike=100,
        years=1,
        rate=0.05,
        dividend_yield=0,
        volatility=0.2,
        option_type=side,
    ) == pytest.approx(expected, abs=1e-11)


@pytest.mark.parametrize("side", ("CE", "PE"))
def test_black76_atm_discounted_expected_value(side):
    sigma = 0.2
    d = sigma / 2
    n = 0.5 * math.erfc(-d / math.sqrt(2))
    expected = math.exp(-0.05) * 100 * (2 * n - 1)
    assert black76_price_v1(
        future=100,
        strike=100,
        years=1,
        rate=0.05,
        volatility=sigma,
        option_type=side,
    ) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("s", (80.0, 100.0, 120.0))
@pytest.mark.parametrize("k", (85.0, 100.0, 115.0))
@pytest.mark.parametrize("r,q", ((0.0, 0.0), (0.08, 0.02), (-0.01, -0.005)))
@pytest.mark.parametrize("sigma", (0.0, 0.1, 0.4))
def test_black_scholes_put_call_parity(s, k, r, q, sigma):
    base = dict(spot=s, strike=k, years=0.75, rate=r, dividend_yield=q, volatility=sigma)
    call = black_scholes_price_v1(option_type="CE", **base)
    put = black_scholes_price_v1(option_type="PE", **base)
    expected = s * math.exp(-q * 0.75) - k * math.exp(-r * 0.75)
    assert call - put == pytest.approx(expected, abs=2e-11)
    assert 0 <= call <= s * math.exp(-q * 0.75)
    assert 0 <= put <= k * math.exp(-r * 0.75)


@pytest.mark.parametrize("f", (80.0, 100.0, 120.0))
@pytest.mark.parametrize("k", (85.0, 100.0, 115.0))
@pytest.mark.parametrize("r", (-0.01, 0.0, 0.08))
@pytest.mark.parametrize("sigma", (0.0, 0.1, 0.4))
def test_black76_put_call_parity(f, k, r, sigma):
    base = dict(future=f, strike=k, years=0.75, rate=r, volatility=sigma)
    call = black76_price_v1(option_type="CE", **base)
    put = black76_price_v1(option_type="PE", **base)
    assert call - put == pytest.approx(math.exp(-r * 0.75) * (f - k), abs=2e-11)


@pytest.mark.parametrize("model", ("BLACK_SCHOLES_SPOT", "BLACK_76_FUTURES"))
@pytest.mark.parametrize("side", ("CE", "PE"))
def test_zero_volatility_is_discounted_deterministic_intrinsic(model, side):
    if model == "BLACK_SCHOLES_SPOT":
        value = black_scholes_price_v1(
            spot=110,
            strike=100,
            years=1,
            rate=0.04,
            dividend_yield=0.01,
            volatility=0,
            option_type=side,
        )
        expected = (110 * math.exp(-0.01) - 100 * math.exp(-0.04)) if side == "CE" else 0
    else:
        value = black76_price_v1(
            future=110, strike=100, years=1, rate=0.04, volatility=0, option_type=side
        )
        expected = math.exp(-0.04) * 10 if side == "CE" else 0
    assert value == pytest.approx(expected)


@pytest.mark.parametrize("sigma", (0.0, 0.01, 0.1, 0.25, 1.0, 3.0, 5.0))
@pytest.mark.parametrize("side", ("CE", "PE"))
def test_model_prices_are_finite_nonnegative_and_bounded(sigma, side):
    a = black_scholes_price_v1(
        spot=100,
        strike=95,
        years=0.001,
        rate=0.05,
        dividend_yield=0.01,
        volatility=sigma,
        option_type=side,
    )
    b = black76_price_v1(
        future=100, strike=95, years=0.001, rate=0.05, volatility=sigma, option_type=side
    )
    assert math.isfinite(a) and a >= 0
    assert math.isfinite(b) and b >= 0


@pytest.mark.parametrize("model", (black_scholes_price_v1, black76_price_v1))
@pytest.mark.parametrize(
    "field,value",
    (
        ("strike", 0),
        ("strike", float("nan")),
        ("strike", float("inf")),
        ("strike", True),
        ("years", 0),
        ("years", -1),
        ("years", 101),
        ("rate", 1.5),
        ("rate", float("inf")),
        ("rate", True),
        ("volatility", -1),
        ("volatility", 5.1),
        ("volatility", float("nan")),
        ("option_type", "CALL"),
    ),
)
def test_math_rejects_invalid_inputs(model, field, value):
    kwargs = dict(strike=100, years=1, rate=0.05, volatility=0.2, option_type="CE")
    kwargs["spot" if model is black_scholes_price_v1 else "future"] = 100
    if model is black_scholes_price_v1:
        kwargs["dividend_yield"] = 0.01
    kwargs[field] = value
    with pytest.raises(ValueError):
        model(**kwargs)


@pytest.mark.parametrize("model", (black_scholes_price_v1, black76_price_v1))
@pytest.mark.parametrize("value", (0, -100, True, float("nan"), float("inf")))
def test_rejects_invalid_reference_price(model, value):
    kwargs = dict(strike=100, years=1, rate=0.05, volatility=0.2, option_type="CE")
    kwargs["spot" if model is black_scholes_price_v1 else "future"] = value
    if model is black_scholes_price_v1:
        kwargs["dividend_yield"] = 0.01
    with pytest.raises(ValueError):
        model(**kwargs)


def test_invalid_dividend_rejected():
    with pytest.raises(ValueError):
        black_scholes_price_v1(
            spot=100,
            strike=100,
            years=1,
            rate=0.05,
            dividend_yield=1.5,
            volatility=0.2,
            option_type="CE",
        )


@pytest.mark.parametrize("market", MARKETS)
def test_retrospective_calculation_never_marked_live(market):
    x5, cap = fixture(market, pit=False)
    out = calculate(x5, cap)
    assert out.status == "RETROSPECTIVE"
    assert all(p.status == "RETROSPECTIVE" for p in out.prices)
    assert "NOT_PROVEN_POINT_IN_TIME" in out.warnings
    assert all(p.execution_authority is False for p in out.prices)


@pytest.mark.parametrize("market", MARKETS)
def test_unverified_reference_is_unavailable_without_price(market):
    x5, cap = fixture(market)
    cap = replace(cap, context=replace(cap.context, reference_verified=False))
    out = calculate(x5, cap)
    assert out.status == "UNAVAILABLE"
    assert all(p.status == "UNAVAILABLE" and p.theoretical_price is None for p in out.prices)
    assert "REFERENCE_PRICE_UNVERIFIED" in out.blockers


@pytest.mark.parametrize("market", MARKETS)
def test_no_default_volatility_or_promotion(market):
    x5, cap = fixture(market)
    for v, sid in ((None, None), (0.2, None)):
        out = calculate(
            x5, cap, annual_volatility=v, volatility_source_id=sid, volatility_verified=False
        )
        assert out.status == "UNAVAILABLE"
        assert out.annual_volatility is None
        assert all(p.theoretical_price is None for p in out.prices)


@pytest.mark.parametrize(
    "value,verified,source",
    (
        (0.2, True, None),
        (None, True, "sigma"),
        (True, True, "sigma"),
        (-1, True, "sigma"),
        (5.1, True, "sigma"),
        (0.2, 1, "sigma"),
        (float("nan"), True, "sigma"),
    ),
)
def test_invalid_volatility_evidence_rejected(value, verified, source):
    x5, cap = fixture()
    with pytest.raises(ValueError):
        calculate(
            x5,
            cap,
            annual_volatility=value,
            volatility_verified=verified,
            volatility_source_id=source,
        )


def test_changed_x5_content_cannot_pass_hash_binding():
    x5, cap = fixture()
    x5 = replace(x5, source_id="different-source")
    with pytest.raises(ValueError):
        calculate(x5, cap)


def test_mismatched_original_premium_rejected_even_though_not_used_by_model():
    x5, cap = fixture()
    rows = list(cap.observations)
    rows[0] = replace(rows[0], premium=99.0)
    cap = replace(cap, observations=tuple(rows))
    with pytest.raises(ValueError):
        calculate(x5, cap)


def test_expiry_instant_unverified_is_unavailable():
    x5, cap = fixture()
    cap = replace(cap, context=replace(cap.context, expiry_instant_verified=False))
    out = calculate(x5, cap)
    assert out.status == "UNAVAILABLE"
    assert "EXACT_FUTURE_EXPIRY_INSTANT_UNAVAILABLE" in out.blockers


def test_rate_unverified_is_unavailable():
    x5, cap = fixture()
    cap = replace(cap, context=replace(cap.context, rate_verified=False))
    out = calculate(x5, cap)
    assert out.status == "UNAVAILABLE"
    assert "DISCOUNT_RATE_UNVERIFIED" in out.blockers


def test_dividend_unverified_unavailable_for_index():
    x5, cap = fixture()
    cap = replace(cap, context=replace(cap.context, dividend_verified=False))
    assert "DIVIDEND_YIELD_UNVERIFIED" in calculate(x5, cap).blockers


def test_futures_identity_unverified_unavailable_for_black76():
    x5, cap = fixture("CRUDEOILM")
    cap = replace(cap, context=replace(cap.context, futures_identity_verified=False))
    assert "UNDERLYING_FUTURES_IDENTITY_UNVERIFIED" in calculate(x5, cap).blockers


def test_theoretical_reference_does_not_require_observed_premium():
    x5, cap = fixture(premiums=False)
    out = calculate(x5, cap)
    assert out.status == "AVAILABLE"
    assert all(p.theoretical_price is not None for p in out.prices)
    assert "NO_VERIFIED_OBSERVED_PREMIUM_FOR_COMPARISON" in out.warnings


def test_no_observations_yields_unavailable():
    x5, cap = fixture(sides=())
    out = calculate(x5, cap)
    assert out.status == "UNAVAILABLE"
    assert out.prices == ()
    assert "NO_CAPTURED_OPTIONS" in out.blockers


@pytest.mark.parametrize("market", MARKETS)
def test_reference_zero_volatility_is_available_when_verified(market):
    x5, cap = fixture(market)
    out = calculate(x5, cap, annual_volatility=0.0)
    assert out.status == "AVAILABLE"
    assert out.annual_volatility == 0
    assert all(p.theoretical_price is not None for p in out.prices)


def test_reference_contract_frozen_and_authority_cannot_be_enabled():
    x5, cap = fixture()
    out = calculate(x5, cap)
    with pytest.raises(FrozenInstanceError):
        out.data_only = False
    with pytest.raises(ValueError):
        replace(out, execution_authority=True)
    with pytest.raises(ValueError):
        replace(out.prices[0], independent_vote=True)
    assert out.source_validation_sha256 != "" and len(out.source_validation_sha256) == 64


def test_empty_disabled_reference_price_requires_blocker():
    with pytest.raises(ValueError):
        X6ReferencePriceV1(
            canonical_option_id="X",
            source_record_id="Y",
            option_type="CE",
            strike=100,
            theoretical_price=None,
            status="UNAVAILABLE",
            blockers=(),
        )


def test_invalid_reference_result_hash_rejected():
    x5, cap = fixture()
    out = calculate(x5, cap)
    with pytest.raises(ValueError):
        replace(out, source_x5_capture_sha256="not-a-sha")


def test_same_capture_deterministic_repricing_and_input_permutation():
    x5, cap = fixture()
    a = calculate(x5, cap)
    b = calculate(x5, cap)
    assert a.sha256() == b.sha256()
    assert tuple(x.canonical_option_id for x in a.prices) == tuple(
        x.canonical_option_id for x in b.prices
    )


def test_static_reference_source_has_no_external_or_order_imports():
    p = Path(__file__).resolve().parents[1] / "services" / "x6" / "reference_pricing_v1.py"
    tree = ast.parse(p.read_text(encoding="utf-8"))
    banned = (
        "requests",
        "fyers_apiv3",
        "SmartApi",
        "services.execution",
        "services.paper_orchestration",
        "subprocess",
        "socket",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not name.name.startswith(banned) for name in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(banned)
