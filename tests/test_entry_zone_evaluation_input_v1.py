from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.contracts import EntryZoneEvaluationInputV1


EVALUATED_AT = datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc)
QUOTE_AT = datetime(2026, 1, 2, 9, 14, tzinfo=timezone.utc)
SOURCE_AT = datetime(2026, 1, 2, 9, 13, tzinfo=timezone.utc)


def _payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "evaluation_id": "entry-evaluation-1",
        "evaluation_result_id": "entry-result-1",
        "evaluated_at": EVALUATED_AT,
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "trade_plan_input_id": "trade-plan-input-1",
        "policy_id": "trade-policy-1",
        "direction": "BULLISH",
        "option_right": "CALL",
        "entry_reference_method": "OPTION_MID",
        "last_traded_price": 100.0,
        "bid_price": 99.0,
        "ask_price": 101.0,
        "signal_reference_price": 100.0,
        "option_mid_price": 100.0,
        "option_quote_timestamp": QUOTE_AT,
        "maximum_entry_premium": 120.0,
        "maximum_spread_fraction": 0.05,
        "planning_allowed": True,
        "blockers": (),
        "warnings": (),
        "source_timestamps": {},
        "metadata": {},
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
        "schema_version": "1.0",
    }
    value.update(overrides)
    return value


def _input(**overrides: object) -> EntryZoneEvaluationInputV1:
    return EntryZoneEvaluationInputV1(**_payload(**overrides))


def test_valid_nifty_bullish_call_uses_canonical_identity() -> None:
    candidate = _input(underlying_symbol="NIFTY 50", exchange="nse")

    assert (candidate.underlying_symbol, candidate.exchange) == ("NIFTY", "NSE")
    assert (candidate.direction, candidate.option_right) == ("BULLISH", "CALL")


def test_valid_sensex_bearish_put() -> None:
    candidate = _input(
        underlying_symbol="SENSEX",
        exchange="BSE",
        direction="BEARISH",
        option_right="PUT",
    )

    assert (candidate.underlying_symbol, candidate.exchange) == ("SENSEX", "BSE")
    assert (candidate.direction, candidate.option_right) == ("BEARISH", "PUT")


@pytest.mark.parametrize(
    "entry_reference_method",
    ("OPTION_MID", "OPTION_ASK", "LAST_TRADED_PRICE", "SIGNAL_REFERENCE", "HYBRID"),
)
def test_accepts_every_controlled_reference_method(entry_reference_method: str) -> None:
    assert _input(entry_reference_method=entry_reference_method).entry_reference_method == entry_reference_method


def test_accepts_complete_and_partial_quote_sets() -> None:
    complete = _input()
    partial = _input(
        last_traded_price=None,
        bid_price=99.0,
        ask_price=None,
        signal_reference_price=None,
        option_mid_price=None,
    )

    assert (complete.bid_price, complete.option_mid_price, complete.ask_price) == (99.0, 100.0, 101.0)
    assert (partial.bid_price, partial.ask_price, partial.option_mid_price) == (99.0, None, None)


@pytest.mark.parametrize("maximum_spread_fraction", (0.0, 1.0))
def test_accepts_absent_and_present_limits(maximum_spread_fraction: float) -> None:
    absent = _input(maximum_entry_premium=None, maximum_spread_fraction=None)
    present = _input(maximum_entry_premium=125, maximum_spread_fraction=maximum_spread_fraction)

    assert (absent.maximum_entry_premium, absent.maximum_spread_fraction) == (None, None)
    assert present.maximum_entry_premium == 125.0
    assert present.maximum_spread_fraction == maximum_spread_fraction


@pytest.mark.parametrize("planning_allowed", (True, False))
def test_preserves_exact_boolean_planning_allowed(planning_allowed: bool) -> None:
    assert _input(planning_allowed=planning_allowed).planning_allowed is planning_allowed


def test_normalizes_diagnostics_in_first_occurrence_order() -> None:
    candidate = _input(
        blockers=("  LIMIT_REACHED  ", "LIMIT_REACHED", "QUOTE_STALE", " LIMIT_REACHED "),
        warnings=("  REVIEW  ", "REVIEW", "LOW_VOLUME"),
    )

    assert candidate.blockers == ("LIMIT_REACHED", "QUOTE_STALE")
    assert candidate.warnings == ("REVIEW", "LOW_VOLUME")


def test_source_timestamps_are_immutable_sorted_and_serialized() -> None:
    candidate = _input(source_timestamps={"quote": QUOTE_AT, "analysis": SOURCE_AT})

    assert tuple(candidate.source_timestamps) == ("analysis", "quote")
    assert candidate.source_timestamps["quote"] == QUOTE_AT
    with pytest.raises(TypeError):
        candidate.source_timestamps["new"] = EVALUATED_AT  # type: ignore[index]
    assert candidate.to_dict()["source_timestamps"] == {
        "analysis": SOURCE_AT.isoformat(),
        "quote": QUOTE_AT.isoformat(),
    }


def test_nested_metadata_is_deeply_immutable_and_json_safe() -> None:
    candidate = _input(
        metadata={
            "nested": {"items": [{"name": "quote", "value": 100.0}, True, None]},
            "tags": ("entry", "paper"),
        }
    )

    assert candidate.metadata["nested"]["items"][0]["name"] == "quote"
    assert candidate.metadata["tags"] == ("entry", "paper")
    with pytest.raises(TypeError):
        candidate.metadata["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.metadata["nested"]["new"] = "value"  # type: ignore[index]


def test_constructor_mappings_are_detached() -> None:
    source_timestamps = {"quote": QUOTE_AT}
    metadata = {"nested": {"values": [1, 2]}}
    candidate = _input(source_timestamps=source_timestamps, metadata=metadata)

    source_timestamps["late"] = EVALUATED_AT
    metadata["nested"]["values"].append(3)
    metadata["new"] = "mutated"

    assert dict(candidate.source_timestamps) == {"quote": QUOTE_AT}
    assert candidate.metadata["nested"]["values"] == (1, 2)
    assert "new" not in candidate.metadata


def test_to_dict_has_deterministic_field_and_mapping_order() -> None:
    candidate = _input(
        source_timestamps={"z-source": QUOTE_AT, "a-source": SOURCE_AT},
        metadata={"z": [2, 1], "a": {"z": 2, "a": 1}},
    )
    first = candidate.to_dict()
    second = candidate.to_dict()

    assert first == second
    assert list(first) == [
        "evaluation_id",
        "evaluation_result_id",
        "evaluated_at",
        "underlying_symbol",
        "exchange",
        "trade_plan_input_id",
        "policy_id",
        "direction",
        "option_right",
        "entry_reference_method",
        "last_traded_price",
        "bid_price",
        "ask_price",
        "signal_reference_price",
        "option_mid_price",
        "option_quote_timestamp",
        "maximum_entry_premium",
        "maximum_spread_fraction",
        "planning_allowed",
        "blockers",
        "warnings",
        "source_timestamps",
        "metadata",
        "execution_mode",
        "live_execution_eligible",
        "schema_version",
    ]
    assert list(first["source_timestamps"]) == ["a-source", "z-source"]
    assert list(first["metadata"]) == ["a", "z"]
    assert list(first["metadata"]["a"]) == ["a", "z"]


def test_to_json_is_deterministic_and_round_trips_to_plain_json() -> None:
    candidate = _input(metadata={"nested": {"values": [1, 2]}})

    assert candidate.to_json() == candidate.to_json()
    assert json.loads(candidate.to_json()) == candidate.to_dict()


def test_semantic_dict_excludes_only_nonsemantic_identity_and_provenance_fields() -> None:
    candidate = _input(source_timestamps={"quote": QUOTE_AT})
    full = candidate.to_dict()
    semantic = candidate.semantic_dict()

    assert {"evaluation_id", "evaluation_result_id", "evaluated_at", "source_timestamps"}.isdisjoint(semantic)
    assert semantic == {
        key: value
        for key, value in full.items()
        if key not in {"evaluation_id", "evaluation_result_id", "evaluated_at", "source_timestamps"}
    }


def test_serialized_outputs_are_fully_detached() -> None:
    candidate = _input(
        blockers=("BLOCK",),
        source_timestamps={"quote": QUOTE_AT},
        metadata={"nested": {"items": [{"value": 1}]}},
    )
    serialized = candidate.to_dict()
    semantic = candidate.semantic_dict()

    serialized["blockers"].append("MUTATED")
    serialized["source_timestamps"]["quote"] = "mutated"
    serialized["metadata"]["nested"]["items"][0]["value"] = 2
    semantic["metadata"]["nested"]["items"][0]["value"] = 3

    assert candidate.blockers == ("BLOCK",)
    assert candidate.source_timestamps["quote"] == QUOTE_AT
    assert candidate.metadata["nested"]["items"][0]["value"] == 1


def test_frozen_equality_public_export_schema_and_paper_defaults() -> None:
    values = _payload()
    for name in ("execution_mode", "live_execution_eligible", "schema_version"):
        values.pop(name)
    first = EntryZoneEvaluationInputV1(**values)
    second = _input()

    assert first == second
    assert first is not second
    assert first.execution_mode == "PAPER"
    assert first.live_execution_eligible is False
    assert first.schema_version == "1.0"
    assert EntryZoneEvaluationInputV1.__module__ == "services.contracts.entry_zone_evaluation_input_v1"
    with pytest.raises(FrozenInstanceError):
        first.policy_id = "other-policy"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("evaluation_id", ""),
        ("evaluation_result_id", " "),
        ("trade_plan_input_id", ""),
        ("policy_id", "  "),
    ),
)
def test_rejects_blank_ids(field_name: str, value: str) -> None:
    with pytest.raises(ValueError):
        _input(**{field_name: value})


@pytest.mark.parametrize("field_name", ("evaluated_at", "option_quote_timestamp"))
def test_rejects_naive_datetimes(field_name: str) -> None:
    with pytest.raises(ValueError):
        _input(**{field_name: datetime(2026, 1, 2, 9, 15)})


@pytest.mark.parametrize(
    ("underlying_symbol", "exchange"),
    (("NIFTY", "BSE"), ("UNSUPPORTED", "NSE")),
)
def test_rejects_invalid_market_identity(underlying_symbol: str, exchange: str) -> None:
    with pytest.raises(ValueError):
        _input(underlying_symbol=underlying_symbol, exchange=exchange)


def test_rejects_invalid_direction_option_right_and_pairing() -> None:
    with pytest.raises(ValueError):
        _input(direction="NEUTRAL")
    with pytest.raises(ValueError):
        _input(option_right="CE")
    with pytest.raises(ValueError):
        _input(direction="BEARISH", option_right="CALL")


def test_rejects_unsupported_reference_method() -> None:
    with pytest.raises(ValueError):
        _input(entry_reference_method="BEST_QUOTE")


@pytest.mark.parametrize("value", (0, -1, True, math.nan, math.inf))
def test_rejects_invalid_prices(value: object) -> None:
    with pytest.raises(ValueError):
        _input(last_traded_price=value)


@pytest.mark.parametrize("value", (0, -1))
def test_rejects_zero_or_negative_premium_cap(value: float) -> None:
    with pytest.raises(ValueError):
        _input(maximum_entry_premium=value)


@pytest.mark.parametrize("value", (-0.01, 1.01))
def test_rejects_spread_fraction_outside_zero_through_one(value: float) -> None:
    with pytest.raises(ValueError):
        _input(maximum_spread_fraction=value)


def test_rejects_invalid_quote_geometry() -> None:
    with pytest.raises(ValueError):
        _input(bid_price=102.0, ask_price=101.0)
    with pytest.raises(ValueError):
        _input(bid_price=99.0, ask_price=101.0, option_mid_price=98.0)
    with pytest.raises(ValueError):
        _input(bid_price=99.0, ask_price=101.0, option_mid_price=102.0)


def test_rejects_non_boolean_planning_allowed() -> None:
    with pytest.raises(TypeError):
        _input(planning_allowed=1)


@pytest.mark.parametrize("field_name", ("blockers", "warnings"))
def test_rejects_non_tuple_or_blank_diagnostics(field_name: str) -> None:
    with pytest.raises(TypeError):
        _input(**{field_name: ["NOT_A_TUPLE"]})
    with pytest.raises(ValueError):
        _input(**{field_name: ("  ",)})


def test_rejects_invalid_source_timestamps() -> None:
    with pytest.raises(TypeError):
        _input(source_timestamps=[("quote", QUOTE_AT)])
    with pytest.raises(ValueError):
        _input(source_timestamps={"quote": datetime(2026, 1, 2, 9, 14)})
    with pytest.raises(ValueError):
        _input(source_timestamps={" ": QUOTE_AT})


@pytest.mark.parametrize(
    "metadata",
    (
        object(),
        {"nested": object()},
        {"value": math.nan},
        {"value": math.inf},
        {1: "non-string key"},
    ),
)
def test_rejects_unsafe_metadata(metadata: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _input(metadata=metadata)


def test_rejects_non_paper_execution_live_eligibility_and_wrong_schema() -> None:
    with pytest.raises(ValueError):
        _input(execution_mode="LIVE")
    with pytest.raises(ValueError):
        _input(live_execution_eligible=True)
    with pytest.raises(ValueError):
        _input(schema_version="2.0")
