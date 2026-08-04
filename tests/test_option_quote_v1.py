from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone
import json
import math

import pytest

from services.contracts.option_quote_v1 import OptionQuoteV1


NOW = datetime(2025, 1, 2, 9, 15, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
MARKETS = (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE"))


def quote(**changes):
    values = {
        "option_quote_id": "quote-1",
        "created_at": NOW,
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "expiry": EXPIRY,
        "strike": 22000.0,
        "option_type": "CALL",
        "ltp": 125.0,
        "bid_price": 124.0,
        "ask_price": 126.0,
        "bid_quantity": 10,
        "ask_quantity": 12,
        "volume": 100,
        "open_interest": 200,
        "change_in_open_interest": -5,
        "implied_volatility": 15.5,
        "underlying_value": 22020.0,
        "source_timestamp": NOW,
        "is_complete": True,
        "provider_name": "fixture-provider",
        "source_record_id": "source-1",
    }
    values.update(changes)
    return OptionQuoteV1(**values)


@pytest.mark.parametrize("symbol,exchange", MARKETS)
@pytest.mark.parametrize("option_type", ("CALL", "PUT"))
def test_supported_identities_and_option_sides_are_preserved(symbol, exchange, option_type):
    value = quote(underlying_symbol=symbol, exchange=exchange, option_type=option_type)
    assert (value.underlying_symbol, value.exchange, value.option_type) == (symbol, exchange, option_type)


def test_schema_and_primitive_serialization_are_deterministic():
    value = quote(blockers=("input_warning",), warnings=("delayed",))
    data = value.to_dict()
    assert data["schema_version"] == "option_quote.v1"
    assert data["created_at"] == NOW.isoformat()
    assert data["expiry"] == EXPIRY.isoformat()
    assert data["blockers"] == ["input_warning"]
    assert data["warnings"] == ["delayed"]
    assert json.loads(json.dumps(data, sort_keys=True, allow_nan=False)) == data


def test_quote_is_frozen_and_slotted():
    value = quote()
    with pytest.raises(FrozenInstanceError):
        value.strike = 1.0
    with pytest.raises((AttributeError, TypeError)):
        value.unexpected = "no"


@pytest.mark.parametrize(
    "field,value",
    (
        ("option_quote_id", ""),
        ("option_quote_id", " "),
        ("provider_name", ""),
        ("provider_name", " "),
        ("source_record_id", ""),
        ("source_record_id", " "),
    ),
)
def test_required_text_values_are_bounded(field, value):
    with pytest.raises(ValueError):
        quote(**{field: value})


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY50", "NSE"),
        ("NIFTY", "BSE"),
        ("SENSEX", "NSE"),
        ("BANKNIFTY", "BSE"),
        ("FINNIFTY", "BSE"),
        ("OTHER", "NSE"),
        ("NIFTY", "nse"),
        (" NIFTY", "NSE"),
    ),
)
def test_identity_must_be_exactly_canonical(symbol, exchange):
    with pytest.raises(ValueError):
        quote(underlying_symbol=symbol, exchange=exchange)


@pytest.mark.parametrize("value", (0, -1, True, float("nan"), float("inf"), -float("inf")))
def test_strike_must_be_positive_finite_number(value):
    with pytest.raises(ValueError):
        quote(strike=value)


@pytest.mark.parametrize("value", ("call", "PUT ", "OTHER", "", None, True))
def test_option_type_is_controlled(value):
    with pytest.raises(ValueError):
        quote(option_type=value)


@pytest.mark.parametrize("field", ("created_at", "source_timestamp"))
@pytest.mark.parametrize("value", (datetime(2025, 1, 2, 9, 15), "2025-01-02", None))
def test_timestamps_must_be_timezone_aware_datetimes(field, value):
    with pytest.raises(ValueError):
        quote(**{field: value})


@pytest.mark.parametrize("field", ("ltp", "bid_price", "ask_price", "implied_volatility", "underlying_value"))
@pytest.mark.parametrize("value", (-1.0, float("nan"), float("inf"), True))
def test_optional_numeric_quote_values_must_be_finite_and_nonnegative(field, value):
    with pytest.raises(ValueError):
        quote(**{field: value})


@pytest.mark.parametrize("field", ("bid_quantity", "ask_quantity", "volume", "open_interest"))
@pytest.mark.parametrize("value", (-1, 1.5, True))
def test_count_values_must_be_nonnegative_integers(field, value):
    with pytest.raises(ValueError):
        quote(**{field: value})


@pytest.mark.parametrize("value", (-10, 0, 10))
def test_change_in_open_interest_is_a_signed_integer(value):
    assert quote(change_in_open_interest=value).change_in_open_interest == value


@pytest.mark.parametrize("value", (-1.5, True, float("nan")))
def test_change_in_open_interest_rejects_non_integer_or_nonfinite_values(value):
    with pytest.raises(ValueError):
        quote(change_in_open_interest=value)


@pytest.mark.parametrize("value", (0, 1, "true", None))
def test_is_complete_requires_actual_boolean(value):
    with pytest.raises(ValueError):
        quote(is_complete=value)


def test_is_complete_allows_false_for_an_incomplete_supplied_quote():
    assert quote(is_complete=False).is_complete is False


@pytest.mark.parametrize("field", ("blockers", "warnings"))
@pytest.mark.parametrize("value", (("",), (1,), ["list"], "text"))
def test_diagnostics_are_bounded_tuples_of_text(field, value):
    with pytest.raises(ValueError):
        quote(**{field: value})


def test_crossed_market_requires_explicit_diagnostic():
    with pytest.raises(ValueError):
        quote(bid_price=126.0, ask_price=124.0)
    assert quote(bid_price=126.0, ask_price=124.0, warnings=("crossed_market",)).warnings == ("crossed_market",)
    assert quote(bid_price=126.0, ask_price=124.0, blockers=("malformed_input",)).blockers == ("malformed_input",)


@pytest.mark.parametrize(
    "changes",
    (
        {"execution_mode": "LIVE"},
        {"execution_mode": ""},
        {"live_execution_eligible": True},
        {"schema_version": "option_quote.v2"},
        {"expiry": NOW},
    ),
)
def test_paper_only_schema_controls_are_enforced(changes):
    with pytest.raises(ValueError):
        quote(**changes)


def test_dataclass_replace_preserves_valid_immutable_data():
    changed = replace(quote(), option_quote_id="quote-2", ltp=None, source_record_id=None)
    assert changed.option_quote_id == "quote-2"
    assert changed.ltp is None
    assert changed.source_record_id is None
