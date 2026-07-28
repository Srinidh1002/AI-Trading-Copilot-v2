"""Behavioral coverage for provider-neutral canonical option-chain normalization."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from services.option_chain_intelligence import (
    CANONICAL_OPTION_CHAIN_RECORD_KEYS,
    normalize_option_chain_records,
)


NOW = datetime(2025, 1, 2, 9, 30, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
_DEFAULT_RECORD_ID = object()


def record(*, strike=100.0, option_type="CALL", source_record_id=_DEFAULT_RECORD_ID, **changes):
    value = {
        "strike": strike,
        "option_type": option_type,
        "ltp": 10.0,
        "bid_price": 9.0,
        "ask_price": 11.0,
        "bid_quantity": 100,
        "ask_quantity": 110,
        "volume": 1000,
        "open_interest": 2000,
        "change_in_open_interest": -25,
        "implied_volatility": 15.0,
        "underlying_value": 20000.0,
        "source_record_id": f"{option_type}-{strike}" if source_record_id is _DEFAULT_RECORD_ID else source_record_id,
        "is_complete": True,
    }
    value.update(changes)
    return value


def complete_records(strikes=(100.0, 137.5, 225.0)):
    # Deliberately reverse input order; only normalized strike rows may sort.
    return tuple(
        reversed(
            [
                record(strike=strike, option_type=side, source_record_id=f"{side}-{number}")
                for number, strike in enumerate(strikes)
                for side in ("CALL", "PUT")
            ]
        )
    )


_DEFAULT_RECORDS = object()


def normalize(records=_DEFAULT_RECORDS, **changes):
    args = {
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "expiry": EXPIRY,
        "underlying_value": 20000.0,
        "source_timestamp": NOW,
        "provider_name": "CANONICAL_TEST",
        "records": complete_records() if records is _DEFAULT_RECORDS else records,
        "clock": lambda: NOW,
    }
    args.update(changes)
    return normalize_option_chain_records(**args)


def test_canonical_vocabulary_is_stable_and_complete():
    assert CANONICAL_OPTION_CHAIN_RECORD_KEYS == (
        "strike", "option_type", "ltp", "bid_price", "ask_price",
        "bid_quantity", "ask_quantity", "volume", "open_interest",
        "change_in_open_interest", "implied_volatility", "underlying_value",
        "source_record_id", "is_complete",
    )


def test_normalizes_unordered_input_to_strictly_ascending_rows_without_grid_inference():
    snapshot = normalize(complete_records((175.0, 100.0, 462.5, 137.5)))
    assert tuple(row.strike for row in snapshot.strike_rows) == (100.0, 137.5, 175.0, 462.5)
    assert snapshot.strike_count == 4
    assert snapshot.complete_pair_count == 4
    assert snapshot.call_only_count == snapshot.put_only_count == 0


@pytest.mark.parametrize(
    "field,value",
    (
        ("ltp", 12.5), ("bid_price", 11.0), ("ask_price", 13.0),
        ("bid_quantity", 12), ("ask_quantity", 13), ("volume", 14),
        ("open_interest", 15), ("change_in_open_interest", -16),
        ("implied_volatility", 17.5), ("underlying_value", 18000.0),
        ("source_record_id", "provider-row"), ("is_complete", False),
    ),
)
def test_preserves_each_canonical_quote_value(field, value):
    quote = normalize((record(**{field: value}),)).strike_rows[0].call
    assert getattr(quote, field) == value


@pytest.mark.parametrize("signed_change", (-1000, -1, 0, 1, 1000))
def test_change_in_open_interest_is_honestly_signed(signed_change):
    quote = normalize((record(change_in_open_interest=signed_change),)).strike_rows[0].call
    assert quote.change_in_open_interest == signed_change


def test_uses_one_shared_created_at_for_snapshot_rows_and_quotes():
    snapshot = normalize()
    assert snapshot.created_at == NOW
    assert {row.call.created_at for row in snapshot.strike_rows if row.call} == {NOW}
    assert {row.put.created_at for row in snapshot.strike_rows if row.put} == {NOW}


def test_preserves_primary_identity_expiry_provider_and_source_timestamp():
    snapshot = normalize()
    assert (snapshot.underlying_symbol, snapshot.exchange, snapshot.expiry) == ("NIFTY", "NSE", EXPIRY)
    assert snapshot.provider_name == "CANONICAL_TEST"
    assert snapshot.source_timestamp == NOW
    assert all(quote.source_timestamp == NOW and quote.provider_name == "CANONICAL_TEST" for row in snapshot.strike_rows for quote in (row.call, row.put) if quote)


def test_never_mutates_caller_records_or_retains_extra_provider_payload():
    supplied = list(complete_records())
    supplied[0] = dict(supplied[0], provider_payload={"secret": "not-retained"})
    records = tuple(supplied)
    before = deepcopy(records)
    snapshot = normalize(records)
    assert records == before
    assert not hasattr(snapshot.strike_rows[0].call, "provider_payload")
    assert "provider_payload" not in snapshot.strike_rows[0].call.to_dict()


def test_default_ids_are_deterministic_for_identical_canonical_input():
    first, second = normalize(), normalize()
    assert first.option_chain_snapshot_id == second.option_chain_snapshot_id
    assert tuple(row.strike_row_id for row in first.strike_rows) == tuple(row.strike_row_id for row in second.strike_rows)
    assert tuple(row.call.option_quote_id for row in first.strike_rows) == tuple(row.call.option_quote_id for row in second.strike_rows)


def test_factories_are_called_in_sorted_quote_then_row_then_snapshot_order():
    quote_ids = iter(("q1", "q2", "q3", "q4"))
    row_ids = iter(("r1", "r2"))
    snapshot_ids = iter(("s1",))
    snapshot = normalize(
        complete_records((150.0, 100.0)),
        option_quote_id_factory=lambda: next(quote_ids),
        strike_row_id_factory=lambda: next(row_ids),
        option_chain_snapshot_id_factory=lambda: next(snapshot_ids),
    )
    assert snapshot.option_chain_snapshot_id == "s1"
    assert tuple(row.strike_row_id for row in snapshot.strike_rows) == ("r1", "r2")
    assert [(row.call.option_quote_id, row.put.option_quote_id) for row in snapshot.strike_rows] == [("q1", "q2"), ("q3", "q4")]


@pytest.mark.parametrize("factory_name", ("option_quote_id_factory", "strike_row_id_factory", "option_chain_snapshot_id_factory"))
@pytest.mark.parametrize("bad_factory", (None, "not-callable", 1))
def test_rejects_invalid_or_empty_factory_results(factory_name, bad_factory):
    if bad_factory is None:
        kwargs = {factory_name: lambda: ""}
    else:
        kwargs = {factory_name: bad_factory}
    with pytest.raises(ValueError):
        normalize((record(),), **kwargs)


@pytest.mark.parametrize("missing_key", CANONICAL_OPTION_CHAIN_RECORD_KEYS)
def test_rejects_each_missing_required_canonical_record_key(missing_key):
    value = record()
    value.pop(missing_key)
    with pytest.raises(ValueError):
        normalize((value,))


@pytest.mark.parametrize("records", ([], {}, "records", (record(), "not-a-mapping"), (1,), None))
def test_rejects_noncanonical_record_containers(records):
    with pytest.raises(ValueError):
        normalize(records)


@pytest.mark.parametrize("strike", (0, -1, float("nan"), float("inf"), True, "100", None))
def test_rejects_invalid_strike_values(strike):
    with pytest.raises(ValueError):
        normalize((record(strike=strike),))


@pytest.mark.parametrize("option_type", ("call", "PUT ", "CE", "PE", "", None, True))
def test_rejects_noncanonical_option_types(option_type):
    with pytest.raises(ValueError):
        normalize((record(option_type=option_type),))


@pytest.mark.parametrize("field", ("ltp", "bid_price", "ask_price", "implied_volatility", "underlying_value"))
@pytest.mark.parametrize("value", (-1, float("nan"), float("inf"), True, "1"))
def test_rejects_invalid_nonnegative_quote_numbers(field, value):
    with pytest.raises(ValueError):
        normalize((record(**{field: value}),))


@pytest.mark.parametrize("field", ("bid_quantity", "ask_quantity", "volume", "open_interest"))
@pytest.mark.parametrize("value", (-1, 1.5, True, "1", float("inf")))
def test_rejects_invalid_nonnegative_integer_quote_counts(field, value):
    with pytest.raises(ValueError):
        normalize((record(**{field: value}),))


@pytest.mark.parametrize("value", (1.5, True, "-1", float("inf")))
def test_rejects_invalid_signed_open_interest_change(value):
    with pytest.raises(ValueError):
        normalize((record(change_in_open_interest=value),))


@pytest.mark.parametrize("value", ("true", 1, None, [], {}))
def test_rejects_nonboolean_completeness(value):
    with pytest.raises(ValueError):
        normalize((record(is_complete=value),))


@pytest.mark.parametrize("value", ("", " ", 1, True, {}))
def test_rejects_invalid_source_record_identifiers(value):
    with pytest.raises(ValueError):
        normalize((record(source_record_id=value),))


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "BSE"), ("BANKNIFTY", "BSE"), ("FINNIFTY", "BSE"),
        ("SENSEX", "NSE"), ("NIFTY 50", "NSE"), ("BANK NIFTY", "NSE"),
        ("FIN NIFTY", "NSE"), ("BSE SENSEX", "BSE"), ("OTHER", "NSE"),
        ("NIFTY", ""), ("", "NSE"), (None, "NSE"), ("NIFTY", None),
    ),
)
def test_rejects_aliases_unsupported_and_mismatched_market_identities(symbol, exchange):
    with pytest.raises(ValueError):
        normalize(underlying_symbol=symbol, exchange=exchange)


@pytest.mark.parametrize("expiry", (NOW, "2025-01-30", None, 1))
def test_rejects_non_date_expiry(expiry):
    with pytest.raises(ValueError):
        normalize(expiry=expiry)


@pytest.mark.parametrize("value", (0, -1, float("nan"), float("inf"), True, "20000"))
def test_rejects_invalid_primary_underlying_value(value):
    with pytest.raises(ValueError):
        normalize(underlying_value=value)


@pytest.mark.parametrize("timestamp", (datetime(2025, 1, 2), "now", None))
def test_rejects_naive_or_non_datetime_source_timestamp(timestamp):
    with pytest.raises(ValueError):
        normalize(source_timestamp=timestamp)


@pytest.mark.parametrize("provider_name", ("", " ", None, 1, True))
def test_rejects_invalid_provider_name(provider_name):
    with pytest.raises(ValueError):
        normalize(provider_name=provider_name)


@pytest.mark.parametrize("clock", ("clock", lambda: datetime(2025, 1, 2), lambda: None))
def test_rejects_invalid_clock_controls(clock):
    with pytest.raises(ValueError):
        normalize(clock=clock)


def test_retains_honestly_call_only_and_put_only_rows_without_synthetic_quotes():
    call_only = normalize(tuple(record(strike=strike, option_type="CALL") for strike in (100.0, 200.0)))
    put_only = normalize(tuple(record(strike=strike, option_type="PUT") for strike in (100.0, 200.0)))
    assert (call_only.call_only_count, call_only.put_only_count, call_only.complete_pair_count) == (2, 0, 0)
    assert (put_only.call_only_count, put_only.put_only_count, put_only.complete_pair_count) == (0, 2, 0)
    assert all(row.put is None for row in call_only.strike_rows)
    assert all(row.call is None for row in put_only.strike_rows)


def test_flags_duplicate_option_sides_deterministically_without_creating_extra_rows():
    snapshot = normalize((record(strike=100.0, option_type="CALL", source_record_id="a"), record(strike=100.0, option_type="CALL", source_record_id="b"), record(strike=100.0, option_type="PUT")))
    assert snapshot.strike_count == 1
    assert snapshot.complete_pair_count == 1
    assert len([warning for warning in snapshot.warnings if warning.startswith("duplicate_option_side:")]) == 1


def test_flags_crossed_market_on_the_quote_for_later_policy_driven_quality_evaluation():
    snapshot = normalize((record(bid_price=12.0, ask_price=11.0),))
    assert snapshot.strike_rows[0].call.warnings == ("crossed_market",)


def test_empty_input_uses_honest_empty_chain_semantics():
    snapshot = normalize(())
    assert snapshot.strike_rows == ()
    assert snapshot.strike_count == 0
    assert snapshot.minimum_strike is snapshot.maximum_strike is None
    assert "empty_option_chain" in snapshot.blockers
