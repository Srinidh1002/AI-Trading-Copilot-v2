from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone
import json

import pytest

from services.contracts.option_chain_snapshot_v1 import OptionChainSnapshotV1
from services.contracts.option_quote_v1 import OptionQuoteV1
from services.contracts.option_strike_row_v1 import OptionStrikeRowV1


NOW = datetime(2025, 1, 2, 9, 15, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
MARKETS = (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE"))


def option_quote(option_type, strike, symbol="NIFTY", exchange="NSE", **changes):
    values = {
        "option_quote_id": f"{option_type}-{strike}", "created_at": NOW,
        "underlying_symbol": symbol, "exchange": exchange, "expiry": EXPIRY,
        "strike": float(strike), "option_type": option_type, "ltp": 125.0,
        "bid_price": 124.0, "ask_price": 126.0, "bid_quantity": 10,
        "ask_quantity": 12, "volume": 100, "open_interest": 200,
        "change_in_open_interest": 0, "implied_volatility": 15.5,
        "underlying_value": 22020.0, "source_timestamp": NOW,
        "is_complete": True, "provider_name": "fixture-provider", "source_record_id": "source-1",
    }
    values.update(changes)
    return OptionQuoteV1(**values)


def strike_row(strike, *, call=True, put=True, symbol="NIFTY", exchange="NSE", expiry=EXPIRY):
    return OptionStrikeRowV1(
        strike_row_id=f"row-{strike}", underlying_symbol=symbol, exchange=exchange,
        expiry=expiry, strike=float(strike),
        call=option_quote("CALL", strike, symbol, exchange, expiry=expiry) if call else None,
        put=option_quote("PUT", strike, symbol, exchange, expiry=expiry) if put else None,
    )


def snapshot(rows=None, **changes):
    rows = (strike_row(21900), strike_row(22000), strike_row(22100, put=False)) if rows is None else tuple(rows)
    values = {
        "option_chain_snapshot_id": "snapshot-1", "created_at": NOW,
        "underlying_symbol": "NIFTY", "exchange": "NSE", "expiry": EXPIRY,
        "underlying_value": 22020.0, "strike_rows": rows, "strike_count": len(rows),
        "complete_pair_count": sum(item.call is not None and item.put is not None for item in rows),
        "call_only_count": sum(item.call is not None and item.put is None for item in rows),
        "put_only_count": sum(item.call is None and item.put is not None for item in rows),
        "minimum_strike": rows[0].strike if rows else None,
        "maximum_strike": rows[-1].strike if rows else None,
        "source_timestamp": NOW, "provider_name": "fixture-provider",
    }
    values.update(changes)
    return OptionChainSnapshotV1(**values)


@pytest.mark.parametrize("symbol,exchange", MARKETS)
@pytest.mark.parametrize("shape", ((True, True), (True, False), (False, True)))
def test_each_canonical_market_preserves_complete_and_missing_side_rows(symbol, exchange, shape):
    call, put = shape
    rows = (strike_row(22000, call=call, put=put, symbol=symbol, exchange=exchange),)
    value = snapshot(rows, underlying_symbol=symbol, exchange=exchange)
    assert (value.underlying_symbol, value.exchange) == (symbol, exchange)
    assert (value.complete_pair_count, value.call_only_count, value.put_only_count) == (
        int(call and put), int(call and not put), int(not call and put),
    )


def test_snapshot_serializes_nested_rows_to_only_primitives():
    value = snapshot(blockers=("source_warning",), warnings=("missing_put",))
    data = value.to_dict()
    assert data["schema_version"] == "option_chain_snapshot.v1"
    assert data["created_at"] == NOW.isoformat()
    assert data["expiry"] == EXPIRY.isoformat()
    assert data["strike_rows"][0]["call"]["option_type"] == "CALL"
    assert data["strike_rows"][2]["put"] is None
    assert json.loads(json.dumps(data, sort_keys=True, allow_nan=False)) == data


def test_snapshot_is_frozen_and_slotted():
    value = snapshot()
    with pytest.raises(FrozenInstanceError):
        value.strike_count = 0
    with pytest.raises((AttributeError, TypeError)):
        value.unexpected = "no"


@pytest.mark.parametrize(
    "symbol,exchange",
    (("NIFTY50", "NSE"), ("NIFTY", "BSE"), ("SENSEX", "NSE"), ("BANKNIFTY", "BSE"), ("OTHER", "NSE"), ("NIFTY", "nse")),
)
def test_snapshot_identity_is_exactly_canonical(symbol, exchange):
    with pytest.raises(ValueError):
        snapshot(underlying_symbol=symbol, exchange=exchange)


@pytest.mark.parametrize("value", ("", " ", 1, None))
def test_snapshot_id_and_provider_name_are_bounded_text(value):
    with pytest.raises(ValueError):
        snapshot(option_chain_snapshot_id=value)
    with pytest.raises(ValueError):
        snapshot(provider_name=value)


@pytest.mark.parametrize("value", (0, -1, True, float("nan"), float("inf")))
def test_supplied_underlying_value_must_be_positive_and_finite(value):
    with pytest.raises(ValueError):
        snapshot(underlying_value=value)


def test_underlying_value_may_be_honestly_unavailable():
    assert snapshot(underlying_value=None).underlying_value is None


@pytest.mark.parametrize("field", ("created_at", "source_timestamp"))
@pytest.mark.parametrize("value", (datetime(2025, 1, 2, 9, 15), "2025-01-02", None))
def test_snapshot_timestamps_must_be_timezone_aware(field, value):
    with pytest.raises(ValueError):
        snapshot(**{field: value})


@pytest.mark.parametrize("value", (NOW, "2025-01-30", None))
def test_snapshot_expiry_must_be_plain_date(value):
    with pytest.raises(ValueError):
        snapshot(expiry=value)


@pytest.mark.parametrize("value", ([], ("not-row",), (object(),)))
def test_strike_rows_must_be_a_tuple_of_rows(value):
    with pytest.raises(ValueError):
        replace(snapshot(), strike_rows=value)


@pytest.mark.parametrize(
    "rows",
    (
        (strike_row(22000), strike_row(21900)),
        (strike_row(22000), strike_row(22000)),
    ),
)
def test_strikes_must_be_strictly_ascending_and_unique(rows):
    with pytest.raises(ValueError):
        snapshot(rows)


@pytest.mark.parametrize(
    "rows",
    (
        (strike_row(22000), strike_row(22100, symbol="SENSEX", exchange="BSE")),
        (strike_row(22000), strike_row(22100, expiry=date(2025, 2, 6))),
    ),
)
def test_all_rows_must_match_snapshot_identity_and_expiry(rows):
    with pytest.raises(ValueError):
        snapshot(rows)


@pytest.mark.parametrize(
    "changes",
    (
        {"strike_count": 2},
        {"complete_pair_count": 1},
        {"call_only_count": 0},
        {"put_only_count": 1},
        {"strike_count": -1},
        {"complete_pair_count": True},
        {"call_only_count": 1.5},
    ),
)
def test_counts_must_be_nonnegative_integers_and_reconcile(changes):
    with pytest.raises(ValueError):
        snapshot(**changes)


@pytest.mark.parametrize(
    "changes",
    (
        {"minimum_strike": None},
        {"maximum_strike": None},
        {"minimum_strike": 21800.0},
        {"maximum_strike": 22200.0},
    ),
)
def test_populated_snapshot_minimum_and_maximum_must_reconcile(changes):
    with pytest.raises(ValueError):
        snapshot(**changes)


def test_empty_snapshot_uses_honest_zero_and_none_semantics():
    value = snapshot(())
    assert (value.strike_count, value.complete_pair_count, value.call_only_count, value.put_only_count) == (0, 0, 0, 0)
    assert (value.minimum_strike, value.maximum_strike) == (None, None)


@pytest.mark.parametrize("changes", ({"minimum_strike": 22000.0}, {"maximum_strike": 22000.0}))
def test_empty_snapshot_rejects_fabricated_range(changes):
    with pytest.raises(ValueError):
        snapshot((), **changes)


@pytest.mark.parametrize("field", ("blockers", "warnings"))
@pytest.mark.parametrize("value", (("",), (1,), ["list"], "text"))
def test_snapshot_diagnostics_are_bounded_text_tuples(field, value):
    with pytest.raises(ValueError):
        snapshot(**{field: value})


@pytest.mark.parametrize(
    "changes",
    (
        {"execution_mode": "LIVE"},
        {"live_execution_eligible": True},
        {"schema_version": "option_chain_snapshot.v2"},
    ),
)
def test_snapshot_is_fixed_to_paper_schema(changes):
    with pytest.raises(ValueError):
        snapshot(**changes)


def test_snapshot_replace_keeps_reconciled_valid_data():
    changed = replace(snapshot(), option_chain_snapshot_id="snapshot-2", warnings=("delayed",))
    assert changed.option_chain_snapshot_id == "snapshot-2"
    assert changed.warnings == ("delayed",)
