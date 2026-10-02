"""X6-A model assumptions, X5 binding, fail-closed provenance and authority tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from math import isclose

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
from services.x6.input_validation_v1 import validate_x6_input_v1

MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
ROOTS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
    "CRUDEOILM": "MCX:CRUDEOILM",
    "GOLDM": "MCX:GOLDM",
    "NATGASMINI": "MCX:NATGASMINI",
}
OPTION_PREFIX = {
    "NIFTY": "NSE:NIFTY",
    "SENSEX": "BSE:SENSEX",
    "CRUDEOILM": "MCX:CRUDEOILM",
    "GOLDM": "MCX:GOLDM",
    "NATGASMINI": "MCX:NATGASMINI",
}
NOW = datetime(2026, 10, 1, 10, 0, tzinfo=IST)
EXPIRY = date(2026, 10, 8)
HASH = "a" * 64


def case(market="NIFTY", sides=("CE", "PE"), point_in_time=True):
    options = tuple(
        X5OptionObservationV1(
            canonical_option_id=f"{market}-{side}-100",
            provider_symbol=f"{OPTION_PREFIX[market]}-FAKE-{side}",
            option_type=side,
            strike=100.0,
            expiry=EXPIRY,
            observed_at=NOW,
            source_record_id=f"{market}-source-{side}",
            ltp=15.0,
            bid_price=10.0,
            ask_price=20.0,
            premium_unit=PRICE_UNITS[market],
            premium_unit_verified=True,
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
        captured_at=NOW if point_in_time else NOW + timedelta(seconds=5),
        observations=options,
        underlying_value=100.0,
        underlying_unit=PRICE_UNITS[market],
        underlying_verified=True,
        capture_verified=True,
        expiry_verified=True,
        timestamp_semantics_verified=True,
        historical_retrieval=not point_in_time,
        point_in_time_verified=point_in_time,
    )
    is_futures = market not in ("NIFTY", "SENSEX")
    ctx = X6PricingContextV1(
        market=market,
        model=MODEL_BY_MARKET[market],
        option_expiry=EXPIRY,
        as_of=NOW,
        option_expiry_at=datetime(
            2026,
            10,
            8,
            23 if is_futures else 15,
            30,
            tzinfo=IST,
        ),
        expiry_source_id="verified-exchange-schedule",
        reference_price=100.0,
        reference_unit=PRICE_UNITS[market],
        reference_source_id="reference-1",
        reference_verified=True,
        premium_unit=PRICE_UNITS[market],
        annual_risk_free_rate=0.06,
        rate_source_id="verified-continuous-rate",
        rate_verified=True,
        annual_dividend_yield=None if is_futures else 0.01,
        dividend_source_id=None if is_futures else "verified-index-yield",
        dividend_verified=False if is_futures else True,
        futures_contract_id=f"MCX:{market}-FUT" if is_futures else None,
        futures_expiry=EXPIRY + timedelta(days=14) if is_futures else None,
        futures_identity_verified=is_futures,
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
                premium_source="LTP",
                premium_verified=True,
            )
            for o in reversed(x5.observations)
        ),
        point_in_time_verified=point_in_time,
    )
    return x5, cap


@pytest.mark.parametrize("market", MARKETS)
def test_exact_five_markets_have_appropriate_models(market):
    x5, cap = case(market)
    result = validate_x6_input_v1(capture=cap, source_x5=x5)
    assert result.model_status == "AVAILABLE"
    assert result.premium_status == "AVAILABLE"
    assert result.status == "AVAILABLE"
    assert cap.context.reference_unit == PRICE_UNITS[market]
    assert result.source_x5_capture_sha256 == x5.sha256()
    assert result.source_capture_sha256 == cap.sha256()
    assert cap.observations[0].option_type == "CE"
    assert cap.observations[-1].option_type == "PE"


@pytest.mark.parametrize("market", MARKETS)
def test_five_market_capture_is_canonical_and_has_deterministic_hash(market):
    _, cap = case(market)
    assert cap.sha256() == cap.sha256()
    assert cap.to_dict()["context"]["market"] == market
    assert all(o.premium_source == "LTP" for o in cap.observations)


@pytest.mark.parametrize("market", MARKETS)
def test_retroactive_download_does_not_claim_point_in_time(market):
    x5, cap = case(market, point_in_time=False)
    r = validate_x6_input_v1(capture=cap, source_x5=x5)
    assert r.time_status == "RETROSPECTIVE"
    assert r.status == "PARTIAL"
    assert "NOT_PROVEN_POINT_IN_TIME" in r.warnings


@pytest.mark.parametrize("market", MARKETS)
def test_missing_exact_expiry_instant_blocks_model(market):
    x5, cap = case(market)
    ctx = replace(cap.context, option_expiry_at=None, expiry_instant_verified=False)
    r = validate_x6_input_v1(capture=replace(cap, context=ctx), source_x5=x5)
    assert r.status == "UNAVAILABLE"
    assert "EXACT_FUTURE_EXPIRY_INSTANT_UNAVAILABLE" in r.blockers


@pytest.mark.parametrize("market", MARKETS)
def test_missing_verified_rate_blocks_model(market):
    x5, cap = case(market)
    ctx = replace(cap.context, annual_risk_free_rate=None, rate_verified=False)
    r = validate_x6_input_v1(capture=replace(cap, context=ctx), source_x5=x5)
    assert "DISCOUNT_RATE_UNVERIFIED" in r.blockers


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_unverified_index_dividend_yield_blocks_model(market):
    x5, cap = case(market)
    ctx = replace(cap.context, annual_dividend_yield=None, dividend_verified=False)
    r = validate_x6_input_v1(capture=replace(cap, context=ctx), source_x5=x5)
    assert "DIVIDEND_YIELD_UNVERIFIED" in r.blockers


@pytest.mark.parametrize("market", ("CRUDEOILM", "GOLDM", "NATGASMINI"))
def test_unverified_underlying_future_identity_blocks_model(market):
    x5, cap = case(market)
    ctx = replace(
        cap.context, futures_contract_id=None, futures_expiry=None, futures_identity_verified=False
    )
    r = validate_x6_input_v1(capture=replace(cap, context=ctx), source_x5=x5)
    assert "UNDERLYING_FUTURES_IDENTITY_UNVERIFIED" in r.blockers


def test_x5_hash_mismatch_is_rejected():
    x5, cap = case()
    with pytest.raises(ValueError, match="SHA-256"):
        validate_x6_input_v1(capture=replace(cap, source_x5_capture_sha256=HASH), source_x5=x5)


def test_x5_metadata_change_causes_hash_mismatch():
    x5, cap = case()
    changed = replace(x5, source_id="tampered-source")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_x6_input_v1(capture=cap, source_x5=changed)


@pytest.mark.parametrize("name,value", (("session_id", "different"), ("capture_id", "different")))
def test_x5_identity_cannot_be_mixed(name, value):
    x5, cap = case()
    with pytest.raises(ValueError, match="mismatch"):
        validate_x6_input_v1(capture=replace(cap, **{name: value}), source_x5=x5)


def test_x5_expiry_cannot_be_mixed():
    x5, cap = case()
    ctx = replace(
        cap.context,
        option_expiry=EXPIRY + timedelta(days=1),
        option_expiry_at=cap.context.option_expiry_at + timedelta(days=1),
    )
    with pytest.raises(ValueError, match="mismatch"):
        validate_x6_input_v1(capture=replace(cap, context=ctx), source_x5=x5)


def test_wrong_model_for_index_is_rejected():
    _, cap = case()
    with pytest.raises(ValueError, match="Model"):
        replace(cap.context, model="BLACK_76_FUTURES")


def test_wrong_model_for_commodity_is_rejected():
    _, cap = case("GOLDM")
    with pytest.raises(ValueError, match="Model"):
        replace(cap.context, model="BLACK_SCHOLES_SPOT")


@pytest.mark.parametrize(
    "field,value",
    (
        ("option_expiry_at", datetime(2026, 10, 8, 15, 30)),
        ("option_expiry_at", datetime(2026, 10, 7, 15, 30, tzinfo=IST)),
        ("reference_unit", "INR_PER_BARREL"),
        ("reference_price", float("nan")),
        ("annual_risk_free_rate", float("inf")),
        ("annual_dividend_yield", float("nan")),
        ("rate_verified", 1),
        ("expiry_instant_verified", "true"),
        ("premium_unit", "LOT_COST_INR"),
        ("annual_risk_free_rate", 6),
        ("annual_dividend_yield", 6),
        ("day_count", "TRADING_DAYS_252"),
        ("rate_convention", "PERCENT_PER_YEAR"),
        ("independent_vote", True),
        ("execution_authority", True),
        ("risk_authority", True),
        ("position_authority", True),
        ("certification_authority", True),
        ("live_execution_eligible", True),
        ("data_only", False),
    ),
)
def test_invalid_model_assumptions_fail_closed(field, value):
    _, cap = case()
    with pytest.raises(ValueError):
        replace(cap.context, **{field: value})


@pytest.mark.parametrize(
    "field,value",
    (
        ("annual_dividend_yield", 0.01),
        ("futures_expiry", EXPIRY - timedelta(days=1)),
        ("futures_contract_id", "bad "),
        ("futures_identity_verified", 1),
    ),
)
def test_black76_cannot_accept_spot_yield_or_invalid_future(field, value):
    _, cap = case("NATGASMINI")
    with pytest.raises(ValueError):
        replace(cap.context, **{field: value})


@pytest.mark.parametrize(
    "field,value",
    (
        ("option_type", "CALL"),
        ("strike", 0),
        ("premium", -1),
        ("premium", float("nan")),
        ("premium_source", "ASK"),
        ("premium_verified", 1),
        ("observed_at", datetime(2026, 10, 1, 10, 0)),
        ("data_only", False),
        ("independent_vote", True),
        ("execution_authority", True),
        ("live_execution_eligible", True),
    ),
)
def test_option_observation_rejects_invalid_values_and_authority(field, value):
    _, cap = case()
    with pytest.raises(ValueError):
        replace(cap.observations[0], **{field: value})


def test_missing_premium_requires_none_source():
    _, cap = case()
    with pytest.raises(ValueError, match="together"):
        replace(cap.observations[0], premium=None)


def test_source_record_id_mismatch_rejected():
    x5, cap = case()
    row = replace(cap.observations[0], source_record_id="other")
    with pytest.raises(ValueError, match="exact X5"):
        validate_x6_input_v1(
            capture=replace(cap, observations=(row,) + cap.observations[1:]), source_x5=x5
        )


def test_premium_mismatch_rejected():
    x5, cap = case()
    row = replace(cap.observations[0], premium=1000.0)
    with pytest.raises(ValueError, match="named X5"):
        validate_x6_input_v1(
            capture=replace(cap, observations=(row,) + cap.observations[1:]), source_x5=x5
        )


def test_mid_price_must_equal_x5_bid_ask_mid():
    x5, cap = case()
    mid = replace(cap.observations[0], premium_source="MID", premium=15.0)
    result = validate_x6_input_v1(
        capture=replace(cap, observations=(mid,) + cap.observations[1:]), source_x5=x5
    )
    assert result.status == "AVAILABLE"


def test_verified_premium_cannot_promote_unverified_x5_unit():
    x5, cap = case()
    rows = (replace(x5.observations[0], premium_unit_verified=False),) + x5.observations[1:]
    modified = replace(x5, observations=rows)
    cap = replace(cap, source_x5_capture_sha256=modified.sha256())
    with pytest.raises(ValueError, match="unverified X5"):
        validate_x6_input_v1(capture=cap, source_x5=modified)


def test_unverified_premium_is_stored_but_not_available():
    x5, cap = case(sides=("CE",))
    row = replace(cap.observations[0], premium_verified=False)
    r = validate_x6_input_v1(capture=replace(cap, observations=(row,)), source_x5=x5)
    assert r.premium_status == "UNAVAILABLE"
    assert r.status == "UNAVAILABLE"


def test_partial_strike_window_does_not_fabricate_second_side():
    x5, cap = case()
    r = validate_x6_input_v1(capture=replace(cap, observations=cap.observations[:1]), source_x5=x5)
    assert r.status == "AVAILABLE"
    assert "PARTIAL_CAPTURED_STRIKE_WINDOW" in r.warnings


def test_no_observations_are_unavailable():
    x5, cap = case()
    r = validate_x6_input_v1(capture=replace(cap, observations=()), source_x5=x5)
    assert r.status == "UNAVAILABLE"
    assert "NO_OBSERVATIONS_IN_CAPTURE" in r.warnings


def test_duplicate_option_input_rejected():
    _, cap = case()
    with pytest.raises(ValueError, match="Duplicate"):
        replace(cap, observations=cap.observations + (cap.observations[0],))


def test_future_dated_option_input_rejected():
    _, cap = case()
    row = replace(cap.observations[0], observed_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="future-dated"):
        replace(cap, observations=(row,) + cap.observations[1:])


def test_unrecognized_or_uppercase_sha_rejected():
    _, cap = case()
    with pytest.raises(ValueError, match="SHA-256"):
        replace(cap, source_x5_capture_sha256="Z" * 64)


def test_x6_cannot_promote_retroactive_source_to_live():
    x5, cap = case(point_in_time=False)
    with pytest.raises(ValueError, match="promote"):
        validate_x6_input_v1(capture=replace(cap, point_in_time_verified=True), source_x5=x5)


def test_future_expiry_without_asof_is_not_guessed():
    _, cap = case()
    assert cap.context.time_to_expiry_years() > 0
    no_proof = replace(cap.context, expiry_instant_verified=False)
    assert no_proof.time_to_expiry_years() is None


def test_act365_calendar_seconds_is_timezone_consistent():
    _, cap = case()
    ctx = cap.context
    expected = (ctx.option_expiry_at - ctx.as_of).total_seconds() / (365 * 86400)
    assert isclose(ctx.time_to_expiry_years(), expected, rel_tol=0, abs_tol=1e-15)
    assert (
        replace(ctx, as_of=ctx.as_of.astimezone(UTC)).time_to_expiry_years()
        == ctx.time_to_expiry_years()
    )


def test_expired_contract_is_unavailable_not_negative_pricing_time():
    x5, cap = case()
    ctx = replace(cap.context, as_of=cap.context.option_expiry_at)
    x5_at_expiry = replace(
        x5,
        as_of=ctx.as_of,
        captured_at=ctx.as_of,
        observations=tuple(replace(o, observed_at=ctx.as_of) for o in x5.observations),
    )
    cap = replace(
        cap,
        context=ctx,
        source_x5_capture_sha256=x5_at_expiry.sha256(),
        observations=tuple(replace(o, observed_at=ctx.as_of) for o in cap.observations),
    )
    result = validate_x6_input_v1(capture=cap, source_x5=x5_at_expiry)
    assert result.status == "UNAVAILABLE"
    assert "EXACT_FUTURE_EXPIRY_INSTANT_UNAVAILABLE" in result.blockers


def test_immutability_and_deterministic_validation_hash():
    x5, cap = case()
    r1 = validate_x6_input_v1(capture=cap, source_x5=x5)
    r2 = validate_x6_input_v1(capture=cap, source_x5=x5)
    assert r1.sha256() == r2.sha256()
    assert r1.to_dict()["status"] == "AVAILABLE"
    with pytest.raises(FrozenInstanceError):
        cap.context.market = "GOLDM"


@pytest.mark.parametrize(
    "field,value",
    (
        ("independent_vote", True),
        ("execution_authority", True),
        ("risk_authority", True),
        ("position_authority", True),
        ("certification_authority", True),
        ("live_execution_eligible", True),
        ("data_only", False),
        ("schema_version", "X6_INPUT_VALIDATION_V2"),
    ),
)
def test_validation_result_authority_cannot_be_enabled(field, value):
    x5, cap = case()
    result = validate_x6_input_v1(capture=cap, source_x5=x5)
    with pytest.raises(ValueError):
        replace(result, **{field: value})


def test_validator_requires_actual_x5_contract():
    _, cap = case()
    with pytest.raises(TypeError):
        validate_x6_input_v1(capture=cap, source_x5={})


def test_input_contract_rejects_bool_numeric_footgun():
    _, cap = case()
    with pytest.raises(ValueError):
        replace(cap.context, reference_price=True)
    with pytest.raises(ValueError):
        replace(cap.observations[0], strike=True)


def test_invalid_source_unit_cannot_be_declared_verified():
    x5, cap = case()
    new_x5 = replace(
        x5, observations=tuple(replace(o, premium_unit="INR_PER_LOT") for o in x5.observations)
    )
    new_cap = replace(cap, source_x5_capture_sha256=new_x5.sha256())
    with pytest.raises(ValueError, match="premium units"):
        validate_x6_input_v1(capture=new_cap, source_x5=new_x5)


def test_unproven_x5_expiry_cannot_be_promoted():
    x5, cap = case()
    new_x5 = replace(x5, expiry_verified=False, point_in_time_verified=False)
    new_cap = replace(cap, source_x5_capture_sha256=new_x5.sha256(), point_in_time_verified=False)
    with pytest.raises(ValueError, match="expiry proof"):
        validate_x6_input_v1(capture=new_cap, source_x5=new_x5)


def test_x5_reference_conflict_is_rejected():
    x5, cap = case()
    new_context = replace(cap.context, reference_price=150.0)
    with pytest.raises(ValueError, match="conflicts"):
        validate_x6_input_v1(capture=replace(cap, context=new_context), source_x5=x5)


def test_x6_validation_status_cannot_claim_live_with_retro_time():
    x5, cap = case(point_in_time=False)
    r = validate_x6_input_v1(capture=cap, source_x5=x5)
    with pytest.raises(ValueError, match="Retrospective"):
        replace(r, status="AVAILABLE")


def test_no_broker_imports_or_order_calls():
    import ast
    from pathlib import Path

    folder = Path(__file__).resolve().parents[1] / "services" / "x6"
    scripts = tuple(folder.glob("*.py"))
    assert {"__init__.py", "contracts_v1.py", "input_validation_v1.py"}.issubset(
        {script.name for script in scripts}
    )
    for script in scripts:
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("services.execution", "services.paper", "src.mcx")
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


def test_invalid_capture_context_cannot_bypass_contract_validation():
    _, cap = case()
    with pytest.raises(ValueError, match="pricing context"):
        replace(cap, context={})


@pytest.mark.parametrize(
    "field,value",
    (
        ("independent_vote", True),
        ("execution_authority", True),
        ("risk_authority", True),
        ("certification_authority", True),
        ("data_only", False),
        ("live_execution_eligible", True),
    ),
)
def test_capture_authority_cannot_be_enabled(field, value):
    _, cap = case()
    with pytest.raises(ValueError):
        replace(cap, **{field: value})


def test_x6_records_do_not_inherit_x5_iv_or_greeks_claims():
    x5, cap = case()
    r = validate_x6_input_v1(capture=cap, source_x5=x5)
    assert r.status == "AVAILABLE"
    assert all("implied_volatility" not in o for o in cap.to_dict()["observations"])
    assert all("delta" not in o for o in cap.to_dict()["observations"])
