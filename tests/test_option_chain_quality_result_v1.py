from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timezone
import json

import pytest

from services.contracts.option_chain_quality_result_v1 import OptionChainQualityResultV1


NOW = datetime(2025, 1, 2, 9, 15, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
MARKETS = (("NIFTY", "NSE"), ("BANKNIFTY", "NSE"), ("FINNIFTY", "NSE"), ("SENSEX", "BSE"))
BLOCKING = ("EMPTY", "STALE", "FUTURE", "INCOMPLETE", "MALFORMED", "UNSUPPORTED", "FAILED")


def quality(**changes):
    values = {
        "option_chain_quality_result_id": "quality-1", "created_at": NOW,
        "option_chain_snapshot_id": "snapshot-1", "underlying_symbol": "NIFTY",
        "exchange": "NSE", "expiry": EXPIRY, "quality_status": "VALID",
        "age_seconds": 5.0, "total_strikes": 3, "complete_pair_count": 2,
        "missing_call_count": 0, "missing_put_count": 1, "malformed_quote_count": 0,
        "duplicate_strike_count": 0, "completeness_ratio": 2 / 3,
    }
    values.update(changes)
    if values["quality_status"] in BLOCKING and "blockers" not in changes:
        values["blockers"] = ("controlled_block",)
    if values["quality_status"] == "VALID_WITH_WARNINGS" and "warnings" not in changes:
        values["warnings"] = ("controlled_warning",)
    return OptionChainQualityResultV1(**values)


@pytest.mark.parametrize("symbol,exchange", MARKETS)
def test_quality_result_preserves_each_canonical_market(symbol, exchange):
    value = quality(underlying_symbol=symbol, exchange=exchange)
    assert (value.underlying_symbol, value.exchange) == (symbol, exchange)


@pytest.mark.parametrize("status", ("VALID", "VALID_WITH_WARNINGS", *BLOCKING))
def test_controlled_quality_statuses_have_explicit_semantics(status):
    kwargs = {"quality_status": status}
    if status == "EMPTY":
        kwargs.update(total_strikes=0, complete_pair_count=0, missing_call_count=0, missing_put_count=0, completeness_ratio=0.0)
    value = quality(**kwargs)
    assert value.quality_status == status


def test_quality_result_serialization_is_primitive_and_deterministic():
    value = quality(quality_status="VALID_WITH_WARNINGS", warnings=("missing_side",))
    data = value.to_dict()
    assert data["schema_version"] == "option_chain_quality_result.v1"
    assert data["created_at"] == NOW.isoformat()
    assert data["expiry"] == EXPIRY.isoformat()
    assert data["warnings"] == ["missing_side"]
    assert json.loads(json.dumps(data, sort_keys=True, allow_nan=False)) == data


def test_quality_result_is_frozen_and_slotted():
    value = quality()
    with pytest.raises(FrozenInstanceError):
        value.age_seconds = 0.0
    with pytest.raises((AttributeError, TypeError)):
        value.unexpected = "no"


@pytest.mark.parametrize(
    "symbol,exchange",
    (("NIFTY50", "NSE"), ("NIFTY", "BSE"), ("SENSEX", "NSE"), ("BANKNIFTY", "BSE"), ("OTHER", "NSE"), ("NIFTY", "nse")),
)
def test_quality_identity_must_be_exactly_canonical(symbol, exchange):
    with pytest.raises(ValueError):
        quality(underlying_symbol=symbol, exchange=exchange)


@pytest.mark.parametrize("field", ("option_chain_quality_result_id", "option_chain_snapshot_id"))
@pytest.mark.parametrize("value", ("", " ", 1, None))
def test_quality_identifiers_are_bounded_text(field, value):
    with pytest.raises(ValueError):
        quality(**{field: value})


@pytest.mark.parametrize("value", (datetime(2025, 1, 2, 9, 15), "2025-01-02", None))
def test_created_at_must_be_timezone_aware(value):
    with pytest.raises(ValueError):
        quality(created_at=value)


@pytest.mark.parametrize("value", (NOW, "2025-01-30", None))
def test_expiry_must_be_plain_date(value):
    with pytest.raises(ValueError):
        quality(expiry=value)


@pytest.mark.parametrize("value", ("", "valid", "PARTIAL", None, True))
def test_quality_status_is_controlled(value):
    with pytest.raises(ValueError):
        quality(quality_status=value)


@pytest.mark.parametrize("age", (-10.0, 0.0, 12.5))
def test_age_seconds_can_honestly_represent_past_present_or_future(age):
    assert quality(age_seconds=age).age_seconds == age


@pytest.mark.parametrize("value", (True, "0", float("nan"), float("inf"), -float("inf")))
def test_age_seconds_must_be_finite_number(value):
    with pytest.raises(ValueError):
        quality(age_seconds=value)


@pytest.mark.parametrize(
    "field",
    ("total_strikes", "complete_pair_count", "missing_call_count", "missing_put_count", "malformed_quote_count", "duplicate_strike_count"),
)
@pytest.mark.parametrize("value", (-1, 1.5, True))
def test_quality_counts_must_be_nonnegative_integers(field, value):
    with pytest.raises(ValueError):
        quality(**{field: value})


@pytest.mark.parametrize(
    "changes",
    (
        {"total_strikes": 4},
        {"complete_pair_count": 1},
        {"missing_call_count": 1},
        {"missing_put_count": 0},
    ),
)
def test_strike_counts_reconcile_exactly(changes):
    with pytest.raises(ValueError):
        quality(**changes)


@pytest.mark.parametrize("value", (-0.1, 1.1, True, float("nan"), float("inf"), "0.5"))
def test_completeness_ratio_must_be_bounded_finite_number(value):
    with pytest.raises(ValueError):
        quality(completeness_ratio=value)


@pytest.mark.parametrize(
    "changes",
    (
        {"completeness_ratio": 0.5},
        {"total_strikes": 0, "complete_pair_count": 0, "missing_call_count": 0, "missing_put_count": 0, "completeness_ratio": 1.0},
        {"total_strikes": 4, "complete_pair_count": 2, "missing_call_count": 1, "missing_put_count": 1, "completeness_ratio": 2 / 3},
    ),
)
def test_completeness_ratio_reconciles_exactly_with_counts(changes):
    with pytest.raises(ValueError):
        quality(**changes)


@pytest.mark.parametrize("status", BLOCKING)
def test_blocking_statuses_require_blockers(status):
    with pytest.raises(ValueError):
        quality(quality_status=status, blockers=())


@pytest.mark.parametrize(
    "changes",
    (
        {"blockers": ("no",)},
        {"warnings": ("no",)},
    ),
)
def test_valid_status_has_neither_blockers_nor_warnings(changes):
    with pytest.raises(ValueError):
        quality(**changes)


@pytest.mark.parametrize(
    "changes",
    (
        {"quality_status": "VALID_WITH_WARNINGS", "warnings": ()},
        {"quality_status": "VALID_WITH_WARNINGS", "blockers": ("no",)},
    ),
)
def test_warning_status_requires_warnings_and_no_blockers(changes):
    with pytest.raises(ValueError):
        quality(**changes)


@pytest.mark.parametrize("field", ("blockers", "warnings"))
@pytest.mark.parametrize("value", (("",), (1,), ["list"], "text"))
def test_quality_diagnostics_are_bounded_text_tuples(field, value):
    with pytest.raises(ValueError):
        quality(**{field: value})


@pytest.mark.parametrize("value", ("option_chain_quality_result.v2", "", None))
def test_quality_schema_version_is_exact(value):
    with pytest.raises(ValueError):
        quality(schema_version=value)


def test_replace_retains_valid_quality_result():
    changed = replace(quality(), option_chain_quality_result_id="quality-2", age_seconds=6.0)
    assert (changed.option_chain_quality_result_id, changed.age_seconds) == ("quality-2", 6.0)
