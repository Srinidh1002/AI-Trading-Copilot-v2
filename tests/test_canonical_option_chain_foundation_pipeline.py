"""Behavioral tests for the supplied-record-only canonical option-chain pipeline."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import importlib

import pytest

from services.contracts import DEFAULT_OPTION_CHAIN_POLICY
from services.option_chain_intelligence import build_canonical_option_chain_foundation


NOW = datetime(2025, 1, 2, 9, 30, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
_DEFAULT_RECORDS = object()


def record(*, strike=100.0, option_type="CALL", source_record_id=None, **changes):
    value = {
        "strike": strike,
        "option_type": option_type,
        "ltp": 10.0,
        "bid_price": 9.0,
        "ask_price": 11.0,
        "bid_quantity": 10,
        "ask_quantity": 11,
        "volume": 100,
        "open_interest": 200,
        "change_in_open_interest": -5,
        "implied_volatility": 15.0,
        "underlying_value": 20000.0,
        "source_record_id": source_record_id if source_record_id is not None else f"{option_type}-{strike}",
        "is_complete": True,
    }
    value.update(changes)
    return value


def records(*, pairs=10, call_only=False, source_timestamp=NOW):
    values = []
    for number in range(pairs):
        strike = 100.0 + number * 37.5
        values.append(record(strike=strike, option_type="CALL", source_record_id=f"c-{number}"))
        if not call_only:
            values.append(record(strike=strike, option_type="PUT", source_record_id=f"p-{number}"))
    # Input order represents an unordered provider-neutral record collection.
    return tuple(reversed(values))


def build(records_value=_DEFAULT_RECORDS, **changes):
    args = {
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "expiry": EXPIRY,
        "underlying_value": 20000.0,
        "source_timestamp": NOW,
        "provider_name": "PIPELINE_TEST",
        "records": records() if records_value is _DEFAULT_RECORDS else records_value,
        "clock": lambda: NOW,
    }
    args.update(changes)
    return build_canonical_option_chain_foundation(**args)


def permissive_policy(**changes):
    values = {
        "minimum_total_strikes": 0,
        "minimum_complete_pairs": 0,
        "minimum_completeness_ratio": 0.0,
        "incomplete_behavior": "ALLOW",
        "missing_side_behavior": "ALLOW",
    }
    values.update(changes)
    return replace(DEFAULT_OPTION_CHAIN_POLICY, **values)


def test_pipeline_returns_linked_valid_snapshot_and_quality_result():
    snapshot, quality = build()
    assert quality.quality_status == "VALID"
    assert quality.option_chain_snapshot_id == snapshot.option_chain_snapshot_id
    assert (snapshot.underlying_symbol, snapshot.exchange, snapshot.expiry) == ("NIFTY", "NSE", EXPIRY)
    assert (quality.underlying_symbol, quality.exchange, quality.expiry) == ("NIFTY", "NSE", EXPIRY)


def test_pipeline_uses_one_outer_clock_value_for_all_created_objects():
    calls = []

    def clock():
        calls.append("clock")
        return NOW

    snapshot, quality = build(clock=clock)
    assert calls == ["clock"]
    assert snapshot.created_at == quality.created_at == NOW
    assert {quote.created_at for row in snapshot.strike_rows for quote in (row.call, row.put) if quote} == {NOW}


def test_pipeline_calls_factories_in_canonical_output_order_once_each():
    quote_ids = iter(f"q-{number}" for number in range(20))
    row_ids = iter(f"r-{number}" for number in range(10))
    snapshot_ids = iter(("snapshot-1",))
    quality_ids = iter(("quality-1",))
    snapshot, quality = build(
        option_quote_id_factory=lambda: next(quote_ids),
        strike_row_id_factory=lambda: next(row_ids),
        option_chain_snapshot_id_factory=lambda: next(snapshot_ids),
        option_chain_quality_result_id_factory=lambda: next(quality_ids),
    )
    assert snapshot.option_chain_snapshot_id == "snapshot-1"
    assert quality.option_chain_quality_result_id == "quality-1"
    assert tuple(row.strike_row_id for row in snapshot.strike_rows) == tuple(f"r-{number}" for number in range(10))
    assert tuple(row.call.option_quote_id for row in snapshot.strike_rows) == tuple(f"q-{number * 2}" for number in range(10))
    assert tuple(row.put.option_quote_id for row in snapshot.strike_rows) == tuple(f"q-{number * 2 + 1}" for number in range(10))


def test_pipeline_normalizes_and_evaluates_exactly_once(monkeypatch):
    module = importlib.import_module("services.option_chain_intelligence.pipeline")
    normalization = importlib.import_module("services.option_chain_intelligence.normalization")
    quality_module = importlib.import_module("services.option_chain_intelligence.quality")
    calls = {"normalization": 0, "quality": 0}
    original_normalize = normalization.normalize_option_chain_records
    original_quality = quality_module.evaluate_option_chain_quality

    def counted_normalize(**kwargs):
        calls["normalization"] += 1
        return original_normalize(**kwargs)

    def counted_quality(**kwargs):
        calls["quality"] += 1
        return original_quality(**kwargs)

    monkeypatch.setattr(normalization, "normalize_option_chain_records", counted_normalize)
    monkeypatch.setattr(quality_module, "evaluate_option_chain_quality", counted_quality)
    module.build_canonical_option_chain_foundation(
        underlying_symbol="NIFTY", exchange="NSE", expiry=EXPIRY,
        underlying_value=20000.0, source_timestamp=NOW, provider_name="PIPELINE_TEST",
        records=records(), clock=lambda: NOW,
    )
    assert calls == {"normalization": 1, "quality": 1}


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "NSE"), ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"), ("SENSEX", "BSE"),
    ),
)
def test_pipeline_preserves_each_authoritative_identity_without_fallback(symbol, exchange):
    snapshot, quality = build(underlying_symbol=symbol, exchange=exchange)
    assert (snapshot.underlying_symbol, snapshot.exchange) == (symbol, exchange)
    assert (quality.underlying_symbol, quality.exchange) == (symbol, exchange)


@pytest.mark.parametrize(
    "source_timestamp,policy,expected_status",
    (
        (NOW, DEFAULT_OPTION_CHAIN_POLICY, "VALID"),
        (NOW - timedelta(seconds=301), DEFAULT_OPTION_CHAIN_POLICY, "STALE"),
        (NOW + timedelta(seconds=6), DEFAULT_OPTION_CHAIN_POLICY, "FUTURE"),
        (NOW + timedelta(seconds=5), DEFAULT_OPTION_CHAIN_POLICY, "VALID"),
    ),
)
def test_pipeline_applies_freshness_and_future_tolerance(source_timestamp, policy, expected_status):
    _, quality = build(source_timestamp=source_timestamp, policy=policy)
    assert quality.quality_status == expected_status


@pytest.mark.parametrize(
    "records_value,policy,expected_status",
    (
        ((), DEFAULT_OPTION_CHAIN_POLICY, "EMPTY"),
        (records(pairs=4), DEFAULT_OPTION_CHAIN_POLICY, "INCOMPLETE"),
        (records(pairs=4), permissive_policy(), "VALID"),
        (records(pairs=10, call_only=True), DEFAULT_OPTION_CHAIN_POLICY, "INCOMPLETE"),
        (records(pairs=10, call_only=True), permissive_policy(missing_side_behavior="WARN"), "VALID_WITH_WARNINGS"),
        (records(pairs=10, call_only=True), permissive_policy(missing_side_behavior="ALLOW"), "VALID"),
        (records(pairs=10, call_only=True), permissive_policy(missing_side_behavior="BLOCK"), "INCOMPLETE"),
    ),
)
def test_pipeline_applies_empty_completeness_and_missing_side_policy(records_value, policy, expected_status):
    _, quality = build(records_value, policy=policy)
    assert quality.quality_status == expected_status


@pytest.mark.parametrize(
    "behavior,expected_status",
    (("BLOCK", "MALFORMED"), ("WARN", "VALID_WITH_WARNINGS"), ("ALLOW", "VALID")),
)
def test_pipeline_applies_crossed_market_policy(behavior, expected_status):
    supplied = list(records())
    supplied[0] = dict(supplied[0], bid_price=12.0, ask_price=11.0)
    _, quality = build(tuple(supplied), policy=permissive_policy(crossed_market_behavior=behavior))
    assert quality.quality_status == expected_status


@pytest.mark.parametrize(
    "behavior,expected_status",
    (("BLOCK", "MALFORMED"), ("WARN", "VALID_WITH_WARNINGS"), ("ALLOW", "VALID")),
)
def test_pipeline_applies_duplicate_side_policy(behavior, expected_status):
    supplied = records() + (record(strike=100.0, option_type="CALL", source_record_id="duplicate"),)
    snapshot, quality = build(supplied, policy=permissive_policy(duplicate_strike_behavior=behavior))
    assert snapshot.strike_count == 10
    assert quality.quality_status == expected_status


@pytest.mark.parametrize(
    "attribute",
    ("pcr", "max_pain", "support", "resistance", "directional_bias", "recommendation", "action", "risk", "execution"),
)
def test_pipeline_outputs_foundation_only_without_option_intelligence_or_execution(attribute):
    snapshot, quality = build()
    assert not hasattr(snapshot, attribute)
    assert not hasattr(quality, attribute)


def test_pipeline_does_not_mutate_or_reorder_caller_records():
    supplied = records()
    before = deepcopy(supplied)
    snapshot, _ = build(supplied)
    assert supplied == before
    assert tuple(row.strike for row in snapshot.strike_rows) == tuple(sorted(record_value["strike"] for record_value in supplied[::2]))


def test_pipeline_is_deterministic_for_identical_input_and_default_factories():
    first = build()
    second = build()
    assert first[0].to_dict() == second[0].to_dict()
    assert first[1].to_dict() == second[1].to_dict()


@pytest.mark.parametrize(
    "field,value",
    (
        ("ltp", 14.5), ("bid_price", 13.0), ("ask_price", 15.0),
        ("bid_quantity", 21), ("ask_quantity", 22), ("volume", 23),
        ("open_interest", 24), ("change_in_open_interest", -25),
        ("implied_volatility", 26.5), ("underlying_value", 19000.0),
        ("source_record_id", "canonical-source-row"), ("is_complete", False),
    ),
)
def test_pipeline_preserves_each_canonical_quote_value(field, value):
    supplied = list(records())
    supplied[0] = dict(supplied[0], **{field: value})
    snapshot, _ = build(tuple(supplied))
    quote = next(
        quote for row in snapshot.strike_rows for quote in (row.call, row.put)
        if quote is not None and quote.source_record_id == (value if field == "source_record_id" else supplied[0]["source_record_id"])
    )
    assert getattr(quote, field) == value


@pytest.mark.parametrize(
    "records_value,policy,expected_counts",
    (
        (records(), DEFAULT_OPTION_CHAIN_POLICY, (10, 10, 0, 0, 1.0)),
        (records(pairs=4), DEFAULT_OPTION_CHAIN_POLICY, (4, 4, 0, 0, 1.0)),
        (records(pairs=10, call_only=True), permissive_policy(missing_side_behavior="ALLOW"), (10, 0, 0, 10, 0.0)),
        (records(pairs=3, call_only=True), permissive_policy(missing_side_behavior="ALLOW"), (3, 0, 0, 3, 0.0)),
        ((), DEFAULT_OPTION_CHAIN_POLICY, (0, 0, 0, 0, 0.0)),
    ),
)
def test_pipeline_quality_counts_reconcile_with_the_normalized_snapshot(records_value, policy, expected_counts):
    snapshot, quality = build(records_value, policy=policy)
    assert (
        snapshot.strike_count,
        quality.total_strikes,
        quality.complete_pair_count,
        quality.missing_call_count,
        quality.missing_put_count,
        quality.completeness_ratio,
    ) == (expected_counts[0], *expected_counts)


@pytest.mark.parametrize(
    "records_value,source_timestamp,policy,expected_status",
    (
        ((), NOW + timedelta(seconds=6), DEFAULT_OPTION_CHAIN_POLICY, "FUTURE"),
        ((), NOW - timedelta(seconds=301), DEFAULT_OPTION_CHAIN_POLICY, "EMPTY"),
        (records(pairs=4), NOW - timedelta(seconds=301), DEFAULT_OPTION_CHAIN_POLICY, "STALE"),
        (records(pairs=4), NOW + timedelta(seconds=6), DEFAULT_OPTION_CHAIN_POLICY, "FUTURE"),
        (records() + (record(strike=100.0, option_type="CALL", source_record_id="duplicate"),), NOW + timedelta(seconds=6), permissive_policy(), "MALFORMED"),
        (tuple([dict(value, bid_price=12.0, ask_price=11.0) if number == 0 else value for number, value in enumerate(records())]), NOW + timedelta(seconds=6), permissive_policy(), "MALFORMED"),
        (records(pairs=10, call_only=True), NOW, permissive_policy(missing_side_behavior="WARN"), "VALID_WITH_WARNINGS"),
        (records(), NOW, permissive_policy(crossed_market_behavior="ALLOW", duplicate_strike_behavior="ALLOW"), "VALID"),
    ),
)
def test_pipeline_applies_documented_quality_status_precedence(records_value, source_timestamp, policy, expected_status):
    _, quality = build(records_value, source_timestamp=source_timestamp, policy=policy)
    assert quality.quality_status == expected_status


@pytest.mark.parametrize(
    "changes",
    (
        {"underlying_symbol": "NIFTY 50", "exchange": "NSE"},
        {"underlying_symbol": "NIFTY", "exchange": "BSE"},
        {"underlying_symbol": "SENSEX", "exchange": "NSE"},
        {"underlying_symbol": None},
        {"exchange": None},
        {"expiry": NOW},
        {"expiry": None},
        {"underlying_value": 0},
        {"underlying_value": float("nan")},
        {"source_timestamp": datetime(2025, 1, 2)},
        {"source_timestamp": None},
        {"provider_name": ""},
        {"provider_name": None},
        {"records": []},
        {"records": None},
        {"records": (record(), "bad")},
    ),
)
def test_pipeline_rejects_invalid_primary_inputs_before_invoking_clock(changes):
    calls = []

    def clock():
        calls.append("called")
        return NOW

    with pytest.raises(ValueError):
        build(clock=clock, **changes)
    assert calls == []


@pytest.mark.parametrize("policy", ("not-policy", 1, object()))
def test_pipeline_rejects_invalid_policy_before_invoking_clock(policy):
    calls = []
    with pytest.raises(ValueError):
        build(policy=policy, clock=lambda: calls.append("called") or NOW)
    assert calls == []


@pytest.mark.parametrize("factory_name", ("option_quote_id_factory", "strike_row_id_factory", "option_chain_snapshot_id_factory", "option_chain_quality_result_id_factory"))
@pytest.mark.parametrize("factory", ("not-callable", 1, True))
def test_pipeline_rejects_invalid_factories_before_invoking_clock(factory_name, factory):
    calls = []
    with pytest.raises(ValueError):
        build(clock=lambda: calls.append("called") or NOW, **{factory_name: factory})
    assert calls == []


@pytest.mark.parametrize("clock", ("not-callable", lambda: datetime(2025, 1, 2), lambda: None))
def test_pipeline_rejects_invalid_clock_values(clock):
    with pytest.raises(ValueError):
        build(clock=clock)


@pytest.mark.parametrize("factory_name", ("option_quote_id_factory", "strike_row_id_factory", "option_chain_snapshot_id_factory", "option_chain_quality_result_id_factory"))
def test_pipeline_rejects_empty_identifier_factory_values(factory_name):
    with pytest.raises(ValueError):
        build(**{factory_name: lambda: ""})


@pytest.mark.parametrize("incomplete_behavior,expected_status", (("BLOCK", "INCOMPLETE"), ("WARN", "VALID_WITH_WARNINGS"), ("ALLOW", "VALID")))
def test_pipeline_applies_incomplete_behavior_without_recalculating_option_intelligence(incomplete_behavior, expected_status):
    policy = permissive_policy(
        minimum_total_strikes=10,
        minimum_complete_pairs=5,
        minimum_completeness_ratio=0.5,
        incomplete_behavior=incomplete_behavior,
    )
    _, quality = build(records(pairs=4), policy=policy)
    assert quality.quality_status == expected_status
