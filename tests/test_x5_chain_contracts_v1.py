"""Offline X5-A five-market identity, provenance, pair integrity and authority tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta

import pytest

from services.x5.chain_validation_v1 import METRICS, validate_x5_chain_v1
from services.x5.contracts_v1 import (
    X5ChainCaptureV1,
    X5ContractV1,
    X5OptionObservationV1,
)

NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
EXPIRY = date(2026, 10, 29)
MARKETS = {
    "NIFTY": ("NFO", "NSE:NIFTY50-INDEX", "NSE:NIFTY"),
    "SENSEX": ("BFO", "BSE:SENSEX-INDEX", "BSE:SENSEX"),
    "CRUDEOILM": ("MCX", "MCX:CRUDEOILM", "MCX:CRUDEOILM"),
    "GOLDM": ("MCX", "MCX:GOLDM", "MCX:GOLDM"),
    "NATGASMINI": ("MCX", "MCX:NATGASMINI", "MCX:NATGASMINI"),
}


def contract(market="NIFTY"):
    exchange, root, _ = MARKETS[market]
    return X5ContractV1(
        market=market,
        provider="FYERS",
        underlying_provider_symbol=root,
        option_exchange=exchange,
        expiry=EXPIRY,
        expiry_source_id="TEST_FYERS_EXPIRY_DATA",
        metadata_status="VERIFIED",
        metadata_source="TEST_MASTER",
    )


def observation(market="NIFTY", side="CE", strike=100.0, *, serial="1"):
    _, _, root = MARKETS[market]
    return X5OptionObservationV1(
        canonical_option_id=f"FYERS:{market}:{serial}:{strike}:{side}",
        provider_symbol=f"{root}{serial}26OCT{int(strike)}{side}",
        option_type=side,
        strike=strike,
        expiry=EXPIRY,
        observed_at=NOW - timedelta(seconds=10),
        source_record_id=f"TEST:{market}:{serial}:{strike}:{side}",
        ltp=10.0,
        bid_price=9.0,
        ask_price=11.0,
        volume=10,
        open_interest=20,
        oi_unit="CONTRACTS",
        volume_unit="CONTRACTS",
        change_in_open_interest=-2,
        implied_volatility=25.0,
        iv_unit="PERCENT",
        premium_unit="INR_PER_OPTION_QUOTE_UNIT",
        delta=0.5 if side == "CE" else -0.5,
        gamma=0.01,
        theta=-0.2,
        vega=0.8,
        oi_unit_verified=True,
        oi_timestamp_verified=True,
        volume_unit_verified=True,
        volume_timestamp_verified=True,
        premium_unit_verified=True,
        oi_change_verified=True,
        oi_change_baseline_id="TEST_COMPARABLE_BASELINE",
        iv_verified=True,
        greeks_verified=True,
    )


def capture(market="NIFTY", observations=None, **kwargs):
    if observations is None:
        observations = (observation(market, "CE"), observation(market, "PE"))
    arguments = dict(
        contract=contract(market),
        session_id="2026-10-01:TEST",
        capture_id="TEST_CAPTURE",
        source_id="TEST_FYERS_RESPONSE",
        as_of=NOW,
        captured_at=NOW,
        observations=tuple(observations),
        underlying_value=100.0,
        underlying_unit={
            "NIFTY": "INDEX_POINTS",
            "SENSEX": "INDEX_POINTS",
            "CRUDEOILM": "INR_PER_BARREL",
            "GOLDM": "INR_PER_10G",
            "NATGASMINI": "INR_PER_MMBTU",
        }[market],
        underlying_verified=True,
        capture_verified=True,
        expiry_verified=True,
        timestamp_semantics_verified=True,
        point_in_time_verified=True,
    )
    arguments.update(kwargs)
    return X5ChainCaptureV1(**arguments)


def readiness(result, name):
    return dict(result.readiness)[name]


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_all_five_markets_have_correct_exchange_and_identity(market):
    c = contract(market)
    assert c.provider == "FYERS"
    assert c.option_exchange == MARKETS[market][0]
    assert c.live_execution_eligible is False and c.execution_authority is False


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_all_five_markets_complete_validated_research(market):
    r = validate_x5_chain_v1(capture(market), max_age_seconds=60)
    assert r.status == "AVAILABLE"
    assert (r.call_count, r.put_count, r.complete_pair_count) == (1, 1, 1)
    assert all(status == "AVAILABLE" for _, status in r.readiness)
    assert not r.blockers


@pytest.mark.parametrize("market", ["BANKNIFTY", "FINNIFTY", "SILVERM", "NATGAS", ""])
def test_out_of_universe_market_rejected(market):
    with pytest.raises(ValueError):
        replace(contract(), market=market)


@pytest.mark.parametrize("market,exchange", [("NIFTY", "BFO"), ("SENSEX", "NFO"), ("GOLDM", "NFO")])
def test_wrong_option_exchange_rejected(market, exchange):
    with pytest.raises(ValueError):
        replace(contract(market), option_exchange=exchange)


def test_wrong_underlying_provider_root_rejected():
    with pytest.raises(ValueError):
        replace(contract(), underlying_provider_symbol="NSE:BANKNIFTY-INDEX")


def test_wrong_provider_rejected():
    with pytest.raises(ValueError):
        replace(contract(), provider="ANGEL")


def test_expiry_must_be_date_not_datetime():
    with pytest.raises(ValueError):
        replace(contract(), expiry=NOW)


@pytest.mark.parametrize(
    "field",
    [
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_contract_cannot_acquire_authority(field):
    with pytest.raises(ValueError):
        replace(contract(), **{field: True})


@pytest.mark.parametrize(
    "field",
    [
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_observation_cannot_acquire_authority(field):
    with pytest.raises(ValueError):
        replace(observation(), **{field: True})


@pytest.mark.parametrize(
    "field",
    [
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_capture_cannot_acquire_authority(field):
    with pytest.raises(ValueError):
        replace(capture(), **{field: True})


def test_validation_cannot_acquire_independent_vote_or_authority():
    r = validate_x5_chain_v1(capture(), max_age_seconds=60)
    for name in (
        "independent_vote",
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ):
        with pytest.raises(ValueError):
            replace(r, **{name: True})


def test_dataclasses_frozen_and_tuple_observations():
    c = capture()
    with pytest.raises(FrozenInstanceError):
        c.capture_id = "CHANGED"
    with pytest.raises(ValueError):
        replace(c, observations=list(c.observations))


def test_capture_hash_independent_of_row_arrival_order():
    original = capture()
    reordered = capture(observations=tuple(reversed(original.observations)))
    assert original.sha256() == reordered.sha256()
    assert (
        validate_x5_chain_v1(original, max_age_seconds=60).sha256()
        == validate_x5_chain_v1(reordered, max_age_seconds=60).sha256()
    )


def test_capture_hash_changes_with_value():
    c = capture()
    altered = replace(c, observations=(replace(c.observations[0], ltp=5), c.observations[1]))
    assert c.sha256() != altered.sha256()


@pytest.mark.parametrize(
    "field,value",
    [
        ("strike", 0),
        ("strike", -1),
        ("strike", float("nan")),
        ("ltp", -1),
        ("ltp", float("inf")),
        ("volume", -5),
        ("open_interest", float("nan")),
        ("implied_volatility", -1),
        ("change_in_open_interest", float("inf")),
        ("delta", -1.2),
        ("gamma", -0.1),
        ("vega", -0.1),
        ("theta", float("nan")),
        ("option_type", "CALL"),
    ],
)
def test_reject_invalid_option_numeric_or_type(field, value):
    with pytest.raises(ValueError):
        replace(observation(), **{field: value})


def test_zero_oi_volume_and_negative_oi_change_are_not_missing():
    row = replace(observation(), open_interest=0, volume=0, change_in_open_interest=-15)
    c = capture(observations=(row, observation(side="PE")))
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.status == "AVAILABLE"
    assert readiness(r, "OI_BUILDUP") == "AVAILABLE"


def test_missing_metrics_remain_unavailable_without_zero_fill():
    row = replace(
        observation(),
        open_interest=None,
        oi_unit_verified=False,
        oi_timestamp_verified=False,
        change_in_open_interest=None,
        oi_change_verified=False,
        oi_change_baseline_id=None,
    )
    r = validate_x5_chain_v1(
        capture(observations=(row, observation(side="PE"))), max_age_seconds=60
    )
    assert r.status == "PARTIAL"
    assert readiness(r, "PCR_OI") == "UNAVAILABLE"
    assert readiness(r, "MAX_PAIN") == "UNAVAILABLE"
    assert readiness(r, "OI_BUILDUP") == "UNAVAILABLE"


@pytest.mark.parametrize("field", ["oi_unit_verified", "oi_timestamp_verified"])
def test_missing_oi_verification_blocks_oi_metrics(field):
    row = replace(observation(), **{field: False}, oi_change_verified=False)
    r = validate_x5_chain_v1(
        capture(observations=(row, observation(side="PE"))), max_age_seconds=60
    )
    assert readiness(r, "PCR_OI") == "UNAVAILABLE"


@pytest.mark.parametrize("field", ["volume_unit_verified", "volume_timestamp_verified"])
def test_missing_volume_verification_blocks_volume_pcr(field):
    row = replace(observation(), **{field: False})
    r = validate_x5_chain_v1(
        capture(observations=(row, observation(side="PE"))), max_age_seconds=60
    )
    assert readiness(r, "PCR_VOLUME") == "UNAVAILABLE"


def test_unverified_premium_unit_blocks_spread():
    row = replace(observation(), premium_unit_verified=False)
    r = validate_x5_chain_v1(
        capture(observations=(row, observation(side="PE"))), max_age_seconds=60
    )
    assert readiness(r, "QUOTE_SPREAD") == "UNAVAILABLE"


def test_unverified_iv_blocks_skew():
    row = replace(observation(), iv_verified=False)
    r = validate_x5_chain_v1(
        capture(observations=(row, observation(side="PE"))), max_age_seconds=60
    )
    assert readiness(r, "IV_SKEW") == "UNAVAILABLE"


def test_mixed_iv_units_block_skew():
    r = validate_x5_chain_v1(
        capture(
            observations=(
                observation(),
                replace(observation(side="PE"), iv_unit="DECIMAL", implied_volatility=0.25),
            )
        ),
        max_age_seconds=60,
    )
    assert readiness(r, "IV_SKEW") == "UNAVAILABLE"


def test_unverified_greeks_block_greeks():
    r = validate_x5_chain_v1(
        capture(
            observations=(replace(observation(), greeks_verified=False), observation(side="PE"))
        ),
        max_age_seconds=60,
    )
    assert readiness(r, "GREEKS") == "UNAVAILABLE"


def test_oi_change_requires_real_baseline():
    with pytest.raises(ValueError):
        replace(observation(), oi_change_baseline_id=None)


def test_verified_oi_change_requires_verified_timestamp():
    with pytest.raises(ValueError):
        replace(observation(), oi_timestamp_verified=False)


def test_verified_iv_requires_declared_unit():
    with pytest.raises(ValueError):
        replace(observation(), iv_unit="UNVERIFIED")


def test_verified_premium_requires_quote():
    with pytest.raises(ValueError):
        replace(observation(), ltp=None, bid_price=None, ask_price=None)


def test_crossed_bid_ask_rejected():
    with pytest.raises(ValueError):
        replace(observation(), bid_price=12, ask_price=10)


@pytest.mark.parametrize("field", ["expiry", "provider_symbol", "observed_at"])
def test_mixed_expiry_exchange_or_future_observation_rejected(field):
    changes = {
        "expiry": date(2026, 11, 5),
        "provider_symbol": "BSE:SENSEX26OCT100PE",
        "observed_at": NOW + timedelta(seconds=1),
    }
    with pytest.raises(ValueError):
        capture(
            observations=(observation(), replace(observation(side="PE"), **{field: changes[field]}))
        )


@pytest.mark.parametrize("field", ["canonical_option_id", "provider_symbol", "source_record_id"])
def test_duplicate_identifiers_rejected(field):
    a = observation()
    b = replace(observation(side="PE"), **{field: getattr(a, field)})
    with pytest.raises(ValueError):
        capture(observations=(a, b))


def test_duplicate_strike_and_side_rejected():
    a = observation()
    b = observation(serial="2")
    with pytest.raises(ValueError):
        capture(observations=(a, b))


@pytest.mark.parametrize("field", ["as_of", "captured_at"])
def test_naive_capture_timestamp_rejected(field):
    with pytest.raises(ValueError):
        capture(**{field: NOW.replace(tzinfo=None)})


def test_retrieval_after_asof_must_be_marked_historical():
    with pytest.raises(ValueError):
        capture(captured_at=NOW + timedelta(minutes=10))


def test_historical_retrieval_cannot_claim_point_in_time():
    with pytest.raises(ValueError):
        capture(historical_retrieval=True, captured_at=NOW + timedelta(minutes=10))


def test_historical_retrieval_is_partial_with_all_metrics_blocked():
    c = capture(
        historical_retrieval=True,
        captured_at=NOW + timedelta(minutes=10),
        point_in_time_verified=False,
    )
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.status == "PARTIAL"
    assert all(value == "UNAVAILABLE" for _, value in r.readiness)
    assert "POINT_IN_TIME_AVAILABILITY_UNPROVEN" in r.warnings


def test_missing_capture_or_expiry_proof_unavailable():
    c = capture(capture_verified=False, expiry_verified=False, point_in_time_verified=False)
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.status == "UNAVAILABLE"
    assert "CAPTURE_UNVERIFIED" in r.blockers and "EXPIRY_UNVERIFIED" in r.blockers


def test_provisional_contract_metadata_unavailable():
    c = capture(contract=replace(contract(), metadata_status="PROVISIONAL"))
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.status == "UNAVAILABLE" and "CONTRACT_METADATA_UNVERIFIED" in r.blockers


def test_empty_chain_unavailable():
    r = validate_x5_chain_v1(capture(observations=()), max_age_seconds=60)
    assert r.status == "UNAVAILABLE" and "EMPTY_CHAIN" in r.blockers


def test_stale_one_side_blocks_entire_chain():
    c = capture(
        observations=(
            replace(observation(), observed_at=NOW - timedelta(minutes=5)),
            observation(side="PE"),
        )
    )
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.status == "UNAVAILABLE" and "STALE_OPTION_ROWS" in r.blockers


@pytest.mark.parametrize("age", [0, -1, float("nan"), float("inf")])
def test_invalid_freshness_budget_rejected(age):
    with pytest.raises(ValueError):
        validate_x5_chain_v1(capture(), max_age_seconds=age)


def test_unpaired_strike_blocks_whole_chain_ratios():
    c = capture(observations=(observation(), observation(side="PE", strike=105)))
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.complete_pair_count == 0 and r.call_only_count == r.put_only_count == 1
    assert readiness(r, "PCR_OI") == "UNAVAILABLE"
    assert "NO_COMPLETE_CE_PE_PAIR" in r.warnings


def test_extra_strike_blocks_whole_chain_ratios():
    c = capture(
        observations=(observation(), observation(side="PE"), observation(strike=105, serial="2"))
    )
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.complete_pair_count == 1 and r.call_only_count == 1
    assert readiness(r, "PCR_OI") == "UNAVAILABLE"


def test_missing_underlying_blocks_relative_levels_not_oi_pcr():
    c = capture(underlying_value=None, underlying_unit=None, underlying_verified=False)
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert readiness(r, "PCR_OI") == "AVAILABLE"
    assert readiness(r, "MAX_PAIN") == "UNAVAILABLE"
    assert readiness(r, "OI_SUPPORT_RESISTANCE") == "UNAVAILABLE"


def test_index_expiry_after_close_is_unavailable():
    expiry = date(2026, 10, 1)
    rows = tuple(replace(row, expiry=expiry) for row in capture().observations)
    c = capture(contract=replace(contract(), expiry=expiry), observations=rows)
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert "INDEX_OPTION_EXPIRY_CUTOFF" in r.blockers


def test_mcx_same_day_expiry_conservative_unavailable():
    expiry = date(2026, 10, 1)
    rows = tuple(replace(row, expiry=expiry) for row in capture("GOLDM").observations)
    c = capture("GOLDM", contract=replace(contract("GOLDM"), expiry=expiry), observations=rows)
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert "MCX_SAME_DAY_EXPIRY_REQUIRES_SEPARATE_REVIEW" in r.blockers


def test_expired_option_chain_unavailable():
    expiry = date(2026, 9, 30)
    rows = tuple(replace(row, expiry=expiry) for row in capture().observations)
    c = capture(contract=replace(contract(), expiry=expiry), observations=rows)
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert "EXPIRED_OPTION_CHAIN" in r.blockers


def test_nonverified_underlying_unit_rejected_for_index():
    with pytest.raises(ValueError):
        capture(underlying_unit="INR_PER_MMBTU")


def test_validation_records_source_capture_hash():
    c = capture()
    r = validate_x5_chain_v1(c, max_age_seconds=60)
    assert r.source_capture_sha256 == c.sha256()
    assert r.sha256() == validate_x5_chain_v1(c, max_age_seconds=60).sha256()
    assert {name for name, _ in r.readiness} == set(METRICS)


def test_metrics_are_readiness_only_not_recommendations():
    r = validate_x5_chain_v1(capture(), max_age_seconds=60)
    assert not r.independent_vote and not r.execution_authority and not r.risk_authority
    assert not r.certification_authority and not r.live_execution_eligible
    assert "trade_action" not in r.to_dict()


@pytest.mark.parametrize(
    "unit_field,verification_field,metric",
    [
        ("oi_unit", "oi_unit_verified", "PCR_OI"),
        ("volume_unit", "volume_unit_verified", "PCR_VOLUME"),
    ],
)
def test_verified_units_are_named(unit_field, verification_field, metric):
    with pytest.raises(ValueError):
        replace(observation(), **{unit_field: "UNVERIFIED", verification_field: True})


@pytest.mark.parametrize(
    "unit_field,metric",
    [
        ("oi_unit", "PCR_OI"),
        ("volume_unit", "PCR_VOLUME"),
        ("premium_unit", "QUOTE_SPREAD"),
    ],
)
def test_mixed_pair_units_block_aggregation(unit_field, metric):
    put = replace(observation(side="PE"), **{unit_field: "DIFFERENT_UNIT"})
    r = validate_x5_chain_v1(capture(observations=(observation(), put)), max_age_seconds=60)
    assert readiness(r, metric) == "UNAVAILABLE"


def test_incomplete_greeks_cannot_claim_full_greeks_readiness():
    put = replace(observation(side="PE"), gamma=None)
    r = validate_x5_chain_v1(capture(observations=(observation(), put)), max_age_seconds=60)
    assert readiness(r, "GREEKS") == "UNAVAILABLE"


@pytest.mark.parametrize(
    "market,expected_unit",
    [
        ("CRUDEOILM", "INR_PER_BARREL"),
        ("GOLDM", "INR_PER_10G"),
        ("NATGASMINI", "INR_PER_MMBTU"),
    ],
)
def test_commodity_underlying_unit_must_match_market(market, expected_unit):
    assert capture(market).underlying_unit == expected_unit
    with pytest.raises(ValueError):
        capture(market, underlying_unit="INR_PER_QUOTE_UNIT")
