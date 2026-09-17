from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone
import json
import math

import pytest

from services.contracts.option_quote_v1 import OptionQuoteV1
from services.contracts.option_strike_row_v1 import OptionStrikeRowV1


NOW = datetime(2025, 1, 2, 9, 15, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
MARKETS = (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE"))


def option_quote(option_type="CALL", **changes):
    values = {
        "option_quote_id": f"quote-{option_type}", "created_at": NOW,
        "underlying_symbol": "NIFTY", "exchange": "NSE", "expiry": EXPIRY,
        "strike": 22000.0, "option_type": option_type, "ltp": 125.0,
        "bid_price": 124.0, "ask_price": 126.0, "bid_quantity": 10,
        "ask_quantity": 12, "volume": 100, "open_interest": 200,
        "change_in_open_interest": 0, "implied_volatility": 15.5,
        "underlying_value": 22020.0, "source_timestamp": NOW,
        "is_complete": True, "provider_name": "fixture-provider", "source_record_id": "source-1",
    }
    values.update(changes)
    return OptionQuoteV1(**values)


def row(**changes):
    values = {
        "strike_row_id": "row-1", "underlying_symbol": "NIFTY", "exchange": "NSE",
        "expiry": EXPIRY, "strike": 22000.0, "call": option_quote("CALL"),
        "put": option_quote("PUT"),
    }
    values.update(changes)
    return OptionStrikeRowV1(**values)


@pytest.mark.parametrize("symbol,exchange", MARKETS)
@pytest.mark.parametrize("has_call,has_put", ((True, True), (True, False), (False, True)))
def test_canonical_rows_support_complete_and_honestly_missing_sides(symbol, exchange, has_call, has_put):
    call = option_quote("CALL", underlying_symbol=symbol, exchange=exchange) if has_call else None
    put = option_quote("PUT", underlying_symbol=symbol, exchange=exchange) if has_put else None
    result = row(underlying_symbol=symbol, exchange=exchange, call=call, put=put)
    assert (result.call is not None, result.put is not None) == (has_call, has_put)


def test_row_serialization_is_nested_primitive_only_and_deterministic():
    value = row(blockers=("row_blocker",), warnings=("row_warning",))
    data = value.to_dict()
    assert data["schema_version"] == "option_strike_row.v1"
    assert data["expiry"] == EXPIRY.isoformat()
    assert data["call"]["option_type"] == "CALL"
    assert data["put"]["option_type"] == "PUT"
    assert data["blockers"] == ["row_blocker"]
    assert json.loads(json.dumps(data, sort_keys=True, allow_nan=False)) == data


def test_row_is_frozen_and_slotted():
    value = row()
    with pytest.raises(FrozenInstanceError):
        value.strike = 1.0
    with pytest.raises((AttributeError, TypeError)):
        value.unexpected = "no"


@pytest.mark.parametrize(
    "symbol,exchange",
    (("NIFTY50", "NSE"), ("NIFTY", "BSE"), ("SENSEX", "NSE"), ("OTHER", "NSE"), ("NIFTY", "nse")),
)
def test_row_identity_is_exactly_canonical(symbol, exchange):
    with pytest.raises(ValueError):
        row(underlying_symbol=symbol, exchange=exchange)


@pytest.mark.parametrize("value", ("", " ", 1, None))
def test_row_id_must_be_nonempty_text(value):
    with pytest.raises(ValueError):
        row(strike_row_id=value)


@pytest.mark.parametrize("value", (0, -1, True, float("nan"), float("inf")))
def test_row_strike_must_be_positive_and_finite(value):
    with pytest.raises(ValueError):
        row(strike=value)


@pytest.mark.parametrize("value", (NOW, "2025-01-30", None))
def test_row_expiry_must_be_plain_date(value):
    with pytest.raises(ValueError):
        row(expiry=value)


def test_row_requires_at_least_one_side():
    with pytest.raises(ValueError):
        row(call=None, put=None)


@pytest.mark.parametrize("field", ("call", "put"))
@pytest.mark.parametrize("value", ("quote", object(), 1))
def test_row_sides_must_be_option_quotes_or_none(field, value):
    with pytest.raises(ValueError):
        row(**{field: value})


@pytest.mark.parametrize(
    "changes",
    (
        {"call": option_quote("PUT")},
        {"put": option_quote("CALL")},
        {"call": option_quote("CALL", underlying_symbol="SENSEX", exchange="BSE")},
        {"put": option_quote("PUT", expiry=date(2025, 2, 6))},
        {"call": option_quote("CALL", strike=22100.0)},
    ),
)
def test_quote_side_identity_expiry_and_strike_must_match_row(changes):
    with pytest.raises(ValueError):
        row(**changes)


@pytest.mark.parametrize("field", ("blockers", "warnings"))
@pytest.mark.parametrize("value", (("",), (1,), ["list"], "text"))
def test_row_diagnostics_are_bounded_text_tuples(field, value):
    with pytest.raises(ValueError):
        row(**{field: value})


@pytest.mark.parametrize("value", ("option_strike_row.v2", "", None))
def test_row_schema_version_is_exact(value):
    with pytest.raises(ValueError):
        row(schema_version=value)


def test_replace_retains_valid_immutable_row():
    changed = replace(row(), strike_row_id="row-2", put=None, warnings=("put_missing",))
    assert changed.strike_row_id == "row-2"
    assert changed.call.option_type == "CALL"
    assert changed.put is None
