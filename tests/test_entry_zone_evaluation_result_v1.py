from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from services.contracts import EntryZoneEvaluationResultV1


EVALUATED_AT = datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc)
QUOTE_AT = datetime(2026, 1, 2, 9, 14, tzinfo=timezone.utc)
SOURCE_AT = datetime(2026, 1, 2, 9, 13, tzinfo=timezone.utc)


def _payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "evaluation_result_id": "entry-result-1",
        "evaluation_id": "entry-evaluation-1",
        "evaluated_at": EVALUATED_AT,
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "direction": "BULLISH",
        "option_right": "CALL",
        "entry_method": "OPTION_MID",
        "selected_reference_source": "OPTION_MID",
        "status": "READY",
        "entry_reference_price": 100.0,
        "entry_zone_lower": 99.0,
        "entry_zone_upper": 101.0,
        "entry_tolerance_fraction": 0.01,
        "maximum_chase_price": 102.0,
        "maximum_entry_premium": 120.0,
        "effective_spread_fraction": 0.02,
        "effective_spread_limit": 0.05,
        "require_limit_entry": True,
        "blockers": (),
        "warnings": (),
        "decision_reasons": (),
        "source_timestamps": {},
        "metadata": {},
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
        "schema_version": "1.0",
    }
    value.update(overrides)
    return value


def _result(**overrides: object) -> EntryZoneEvaluationResultV1:
    return EntryZoneEvaluationResultV1(**_payload(**overrides))


def _absent_price_group() -> dict[str, object]:
    return {
        "selected_reference_source": None,
        "entry_reference_price": None,
        "entry_zone_lower": None,
        "entry_zone_upper": None,
        "entry_tolerance_fraction": None,
        "maximum_chase_price": None,
    }


def test_ready_nifty_bullish_call_uses_canonical_identity() -> None:
    result = _result(underlying_symbol="NIFTY 50", exchange="nse")

    assert (result.underlying_symbol, result.exchange) == ("NIFTY", "NSE")
    assert (result.direction, result.option_right, result.status) == ("BULLISH", "CALL", "READY")


def test_ready_sensex_bearish_put() -> None:
    result = _result(
        underlying_symbol="SENSEX",
        exchange="BSE",
        direction="BEARISH",
        option_right="PUT",
        entry_method="OPTION_ASK",
        selected_reference_source="OPTION_ASK",
    )

    assert (result.underlying_symbol, result.exchange) == ("SENSEX", "BSE")
    assert (result.direction, result.option_right) == ("BEARISH", "PUT")


@pytest.mark.parametrize(
    ("entry_method", "selected_reference_source"),
    (
        ("OPTION_MID", "OPTION_MID"),
        ("OPTION_ASK", "OPTION_ASK"),
        ("LAST_TRADED_PRICE", "LAST_TRADED_PRICE"),
        ("SIGNAL_REFERENCE", "SIGNAL_REFERENCE"),
        ("HYBRID", "OPTION_MID"),
    ),
)
def test_accepts_every_controlled_entry_method(
    entry_method: str,
    selected_reference_source: str,
) -> None:
    result = _result(
        entry_method=entry_method,
        selected_reference_source=selected_reference_source,
    )

    assert (result.entry_method, result.selected_reference_source) == (
        entry_method,
        selected_reference_source,
    )


def test_blocked_and_no_entry_allow_absent_or_complete_price_groups() -> None:
    blocked_absent = _result(status="BLOCKED", blockers=("PREMIUM_LIMIT",), **_absent_price_group())
    blocked_complete = _result(status="BLOCKED", blockers=("PREMIUM_LIMIT",))
    no_entry_absent = _result(status="NO_ENTRY", decision_reasons=("NO_SETUP",), **_absent_price_group())
    no_entry_complete = _result(status="NO_ENTRY", decision_reasons=("NO_SETUP",))

    assert blocked_absent.entry_reference_price is None
    assert blocked_complete.entry_reference_price == 100.0
    assert no_entry_absent.entry_reference_price is None
    assert no_entry_complete.entry_reference_price == 100.0


def test_ready_allows_warnings_and_absent_or_satisfied_constraint_evidence() -> None:
    absent = _result(
        maximum_entry_premium=None,
        effective_spread_fraction=None,
        effective_spread_limit=None,
        warnings=(" REVIEW ",),
    )
    exact_limit = _result(effective_spread_fraction=0.05, effective_spread_limit=0.05)

    assert absent.warnings == ("REVIEW",)
    assert absent.maximum_entry_premium is None
    assert absent.spread_within_limit is None
    assert exact_limit.spread_within_limit is True


def test_geometry_properties_for_complete_and_absent_groups() -> None:
    complete = _result()
    absent = _result(status="BLOCKED", blockers=("NO_REFERENCE",), **_absent_price_group())

    assert complete.zone_width == 2.0
    assert complete.lower_distance_fraction == 0.01
    assert complete.upper_distance_fraction == 0.01
    assert (absent.zone_width, absent.lower_distance_fraction, absent.upper_distance_fraction) == (None, None, None)


def test_diagnostics_are_trimmed_deduplicated_and_immutable() -> None:
    result = _result(
        status="BLOCKED",
        blockers=("  LIMIT  ", "LIMIT", "QUOTE", " LIMIT "),
        warnings=(" REVIEW ", "REVIEW", "LOW_VOLUME"),
        decision_reasons=("  RETAINED  ", "RETAINED"),
    )

    assert result.blockers == ("LIMIT", "QUOTE")
    assert result.warnings == ("REVIEW", "LOW_VOLUME")
    assert result.decision_reasons == ("RETAINED",)


def test_source_timestamps_are_immutable_sorted_and_serialized() -> None:
    result = _result(source_timestamps={"quote": QUOTE_AT, "analysis": SOURCE_AT})

    assert tuple(result.source_timestamps) == ("analysis", "quote")
    with pytest.raises(TypeError):
        result.source_timestamps["new"] = EVALUATED_AT  # type: ignore[index]
    assert result.to_dict()["source_timestamps"] == {
        "analysis": SOURCE_AT.isoformat(),
        "quote": QUOTE_AT.isoformat(),
    }


def test_nested_metadata_is_deeply_immutable_and_json_safe() -> None:
    result = _result(
        metadata={
            "nested": {"items": [{"name": "quote", "value": 100.0}, True, None]},
            "tags": ("entry", "paper"),
        }
    )

    assert result.metadata["nested"]["items"][0]["name"] == "quote"
    assert result.metadata["tags"] == ("entry", "paper")
    with pytest.raises(TypeError):
        result.metadata["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        result.metadata["nested"]["new"] = "value"  # type: ignore[index]


def test_constructor_mappings_are_detached() -> None:
    source_timestamps = {"quote": QUOTE_AT}
    metadata = {"nested": {"values": [1, 2]}}
    result = _result(source_timestamps=source_timestamps, metadata=metadata)

    source_timestamps["late"] = EVALUATED_AT
    metadata["nested"]["values"].append(3)
    metadata["new"] = "mutated"

    assert dict(result.source_timestamps) == {"quote": QUOTE_AT}
    assert result.metadata["nested"]["values"] == (1, 2)
    assert "new" not in result.metadata


def test_to_dict_has_deterministic_field_and_mapping_order() -> None:
    result = _result(
        source_timestamps={"z-source": QUOTE_AT, "a-source": SOURCE_AT},
        metadata={"z": [2, 1], "a": {"z": 2, "a": 1}},
    )
    first = result.to_dict()
    second = result.to_dict()

    assert first == second
    assert list(first) == [
        "evaluation_result_id",
        "evaluation_id",
        "evaluated_at",
        "underlying_symbol",
        "exchange",
        "direction",
        "option_right",
        "entry_method",
        "selected_reference_source",
        "status",
        "entry_reference_price",
        "entry_zone_lower",
        "entry_zone_upper",
        "entry_tolerance_fraction",
        "maximum_chase_price",
        "maximum_entry_premium",
        "effective_spread_fraction",
        "effective_spread_limit",
        "require_limit_entry",
        "blockers",
        "warnings",
        "decision_reasons",
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
    result = _result(metadata={"nested": {"values": [1, 2]}})

    assert result.to_json() == result.to_json()
    assert json.loads(result.to_json()) == result.to_dict()


def test_semantic_dict_excludes_only_nonsemantic_identity_and_provenance_fields() -> None:
    result = _result(source_timestamps={"quote": QUOTE_AT})
    full = result.to_dict()
    semantic = result.semantic_dict()

    excluded = {"evaluation_result_id", "evaluation_id", "evaluated_at", "source_timestamps"}
    assert excluded.isdisjoint(semantic)
    assert semantic == {key: value for key, value in full.items() if key not in excluded}


def test_serialized_outputs_are_fully_detached() -> None:
    result = _result(
        blockers=(),
        source_timestamps={"quote": QUOTE_AT},
        metadata={"nested": {"items": [{"value": 1}]}},
    )
    serialized = result.to_dict()
    semantic = result.semantic_dict()

    serialized["warnings"].append("MUTATED")
    serialized["source_timestamps"]["quote"] = "mutated"
    serialized["metadata"]["nested"]["items"][0]["value"] = 2
    semantic["metadata"]["nested"]["items"][0]["value"] = 3

    assert result.warnings == ()
    assert result.source_timestamps["quote"] == QUOTE_AT
    assert result.metadata["nested"]["items"][0]["value"] == 1


def test_frozen_equality_public_export_schema_and_paper_defaults() -> None:
    values = _payload()
    for name in ("execution_mode", "live_execution_eligible", "schema_version"):
        values.pop(name)
    first = EntryZoneEvaluationResultV1(**values)
    second = _result()

    assert first == second
    assert first is not second
    assert first.execution_mode == "PAPER"
    assert first.live_execution_eligible is False
    assert first.schema_version == "1.0"
    assert EntryZoneEvaluationResultV1.__module__ == "services.contracts.entry_zone_evaluation_result_v1"
    with pytest.raises(FrozenInstanceError):
        first.status = "BLOCKED"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("evaluation_result_id", ""), ("evaluation_id", "  ")),
)
def test_rejects_blank_ids(field_name: str, value: str) -> None:
    with pytest.raises(ValueError):
        _result(**{field_name: value})


def test_rejects_naive_time_invalid_identity_direction_right_method_source_and_status() -> None:
    with pytest.raises(ValueError):
        _result(evaluated_at=datetime(2026, 1, 2, 9, 15))
    with pytest.raises(ValueError):
        _result(underlying_symbol="NIFTY", exchange="BSE")
    with pytest.raises(ValueError):
        _result(direction="NEUTRAL")
    with pytest.raises(ValueError):
        _result(option_right="CE")
    with pytest.raises(ValueError):
        _result(direction="BEARISH", option_right="CALL")
    with pytest.raises(ValueError):
        _result(entry_method="BEST_QUOTE")
    with pytest.raises(ValueError):
        _result(selected_reference_source="HYBRID")
    with pytest.raises(ValueError):
        _result(status="UNAVAILABLE")


def test_rejects_invalid_status_price_group_combinations() -> None:
    with pytest.raises(ValueError):
        _result(**_absent_price_group())
    with pytest.raises(ValueError):
        _result(entry_zone_lower=None)
    with pytest.raises(ValueError):
        _result(blockers=("BLOCK",))
    with pytest.raises(ValueError):
        _result(status="BLOCKED")
    with pytest.raises(ValueError):
        _result(status="NO_ENTRY")
    for status, extra in (("BLOCKED", {"blockers": ("BLOCK",)}), ("NO_ENTRY", {"decision_reasons": ("NO_SETUP",)})):
        with pytest.raises(ValueError):
            _result(status=status, entry_zone_lower=None, **extra)


@pytest.mark.parametrize(
    ("field_name", "value"),
    tuple((field_name, value) for field_name in ("entry_reference_price", "entry_zone_lower", "entry_zone_upper", "maximum_chase_price") for value in (0, -1)),
)
def test_rejects_zero_or_negative_price_geometry(field_name: str, value: float) -> None:
    with pytest.raises(ValueError):
        _result(**{field_name: value})


@pytest.mark.parametrize("value", (True, math.nan, math.inf))
def test_rejects_bool_nan_and_infinite_numeric_values(value: object) -> None:
    with pytest.raises(ValueError):
        _result(entry_reference_price=value)


def test_rejects_invalid_geometry_ordering_and_distances() -> None:
    with pytest.raises(ValueError):
        _result(entry_zone_lower=101.0, entry_zone_upper=101.0)
    with pytest.raises(ValueError):
        _result(entry_reference_price=98.0)
    with pytest.raises(ValueError):
        _result(entry_reference_price=102.0)
    with pytest.raises(ValueError):
        _result(maximum_chase_price=100.0)


@pytest.mark.parametrize("value", (-0.01, 1.01))
def test_rejects_invalid_tolerance(value: float) -> None:
    with pytest.raises(ValueError):
        _result(entry_tolerance_fraction=value)


@pytest.mark.parametrize("value", (0, -1, True, math.nan, math.inf))
def test_rejects_invalid_premium_cap(value: object) -> None:
    with pytest.raises(ValueError):
        _result(maximum_entry_premium=value)


@pytest.mark.parametrize("maximum_entry_premium", (99.0, 100.0, 101.0))
def test_ready_rejects_reference_upper_or_chase_above_premium_cap(maximum_entry_premium: float) -> None:
    with pytest.raises(ValueError):
        _result(maximum_entry_premium=maximum_entry_premium)


@pytest.mark.parametrize("effective_spread_fraction", (-0.01, True, math.nan, math.inf))
def test_rejects_invalid_effective_spread_fraction(effective_spread_fraction: object) -> None:
    with pytest.raises(ValueError):
        _result(effective_spread_fraction=effective_spread_fraction)


@pytest.mark.parametrize("effective_spread_limit", (-0.01, 1.01, True, math.nan, math.inf))
def test_rejects_invalid_effective_spread_limit(effective_spread_limit: object) -> None:
    with pytest.raises(ValueError):
        _result(effective_spread_limit=effective_spread_limit)


def test_ready_rejects_spread_above_limit_and_non_boolean_limit_entry_requirement() -> None:
    with pytest.raises(ValueError):
        _result(effective_spread_fraction=0.06, effective_spread_limit=0.05)
    with pytest.raises(TypeError):
        _result(require_limit_entry=1)


@pytest.mark.parametrize("field_name", ("blockers", "warnings", "decision_reasons"))
def test_rejects_non_tuple_or_blank_diagnostics(field_name: str) -> None:
    with pytest.raises(TypeError):
        _result(**{field_name: ["NOT_A_TUPLE"]})
    with pytest.raises(ValueError):
        _result(**{field_name: ("  ",)})


def test_rejects_invalid_source_timestamps() -> None:
    with pytest.raises(TypeError):
        _result(source_timestamps=[("quote", QUOTE_AT)])
    with pytest.raises(ValueError):
        _result(source_timestamps={"quote": datetime(2026, 1, 2, 9, 14)})
    with pytest.raises(ValueError):
        _result(source_timestamps={" ": QUOTE_AT})


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
        _result(metadata=metadata)


def test_rejects_non_paper_execution_live_eligibility_and_wrong_schema() -> None:
    with pytest.raises(ValueError):
        _result(execution_mode="LIVE")
    with pytest.raises(ValueError):
        _result(live_execution_eligible=True)
    with pytest.raises(ValueError):
        _result(schema_version="2.0")
