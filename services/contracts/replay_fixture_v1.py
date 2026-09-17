"""Versioned, offline fixture contract for canonical pipeline replay."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from .market_snapshot_v1 import MarketSnapshotV1


class ReplayFixtureValidationError(ValueError):
    """Raised when a replay fixture does not use the v1 contract."""


@dataclass(frozen=True, slots=True)
class ReplayExpectationsV1:
    """Stable canonical decision outcomes asserted by a replay fixture.

    IDs and timestamps are deliberately not replay expectations because the
    canonical contracts generate them at run time.
    """

    action: str | None = None
    authorization_status: str | None = None
    execution_status: str | None = None
    direction: str | None = None
    validation_passed: bool | None = None
    data_health_status: str | None = None
    blocking_reasons: tuple[str, ...] | None = None
    internal_errors: tuple[str, ...] | None = None
    expected_action: str | None = None
    expected_direction: str | None = None
    expected_authorization: str | None = None
    expected_execution_status: str | None = None
    expected_data_health_status: str | None = None
    expected_validation_passed: bool | None = None
    expected_market_regime: str | None = None
    expected_trend_strength: str | None = None
    expected_volatility_state: str | None = None
    expected_option_type: str | None = None
    expected_trade_plan_present: bool | None = None
    expected_blockers: tuple[str, ...] | None = None
    expected_missing_sources: tuple[str, ...] | None = None
    expected_stale_sources: tuple[str, ...] | None = None
    confidence_min: float | None = None
    confidence_max: float | None = None
    technical_score_min: float | None = None
    technical_score_max: float | None = None
    options_score_min: float | None = None
    options_score_max: float | None = None
    institutional_score_min: float | None = None
    institutional_score_max: float | None = None

    def to_dict(self) -> dict[str, Any]:
        values = {
            "action": self.action,
            "authorization_status": self.authorization_status,
            "execution_status": self.execution_status,
            "direction": self.direction,
            "validation_passed": self.validation_passed,
            "data_health_status": self.data_health_status,
            "blocking_reasons": list(self.blocking_reasons) if self.blocking_reasons is not None else None,
            "internal_errors": list(self.internal_errors) if self.internal_errors is not None else None,
        }
        for name in self.__dataclass_fields__:
            if name in values:
                continue
            value = getattr(self, name)
            values[name] = list(value) if isinstance(value, tuple) else value
        return values

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReplayExpectationsV1":
        if not isinstance(payload, Mapping):
            raise ReplayFixtureValidationError("expectations must be a JSON object.")
        unknown = set(payload) - set(cls.__dataclass_fields__)
        if unknown:
            raise ReplayFixtureValidationError(
                f"Unsupported replay expectation fields: {', '.join(sorted(unknown))}."
            )
        return cls(
            action=_optional_string(payload.get("action")),
            authorization_status=_optional_string(payload.get("authorization_status")),
            execution_status=_optional_string(payload.get("execution_status")),
            direction=_optional_string(payload.get("direction")),
            validation_passed=_optional_bool(payload.get("validation_passed")),
            data_health_status=_optional_string(payload.get("data_health_status")),
            blocking_reasons=_optional_strings(payload.get("blocking_reasons"), "blocking_reasons"),
            internal_errors=_optional_strings(payload.get("internal_errors"), "internal_errors"),
            expected_action=_optional_string(payload.get("expected_action")),
            expected_direction=_optional_string(payload.get("expected_direction")),
            expected_authorization=_optional_string(payload.get("expected_authorization")),
            expected_execution_status=_optional_string(payload.get("expected_execution_status")),
            expected_data_health_status=_optional_string(payload.get("expected_data_health_status")),
            expected_validation_passed=_optional_bool(payload.get("expected_validation_passed")),
            expected_market_regime=_optional_string(payload.get("expected_market_regime")),
            expected_trend_strength=_optional_string(payload.get("expected_trend_strength")),
            expected_volatility_state=_optional_string(payload.get("expected_volatility_state")),
            expected_option_type=_optional_string(payload.get("expected_option_type")),
            expected_trade_plan_present=_optional_bool(payload.get("expected_trade_plan_present")),
            expected_blockers=_optional_strings(payload.get("expected_blockers"), "expected_blockers"),
            expected_missing_sources=_optional_strings(payload.get("expected_missing_sources"), "expected_missing_sources"),
            expected_stale_sources=_optional_strings(payload.get("expected_stale_sources"), "expected_stale_sources"),
            confidence_min=_optional_number(payload.get("confidence_min"), "confidence_min"),
            confidence_max=_optional_number(payload.get("confidence_max"), "confidence_max"),
            technical_score_min=_optional_number(payload.get("technical_score_min"), "technical_score_min"),
            technical_score_max=_optional_number(payload.get("technical_score_max"), "technical_score_max"),
            options_score_min=_optional_number(payload.get("options_score_min"), "options_score_min"),
            options_score_max=_optional_number(payload.get("options_score_max"), "options_score_max"),
            institutional_score_min=_optional_number(payload.get("institutional_score_min"), "institutional_score_min"),
            institutional_score_max=_optional_number(payload.get("institutional_score_max"), "institutional_score_max"),
        )


@dataclass(frozen=True, slots=True)
class ReplayFixtureV1:
    """A saved snapshot and explicit expected canonical decision outcomes."""

    fixture_id: str
    name: str
    snapshot: MarketSnapshotV1
    expectations: ReplayExpectationsV1
    schema_version: str = "replay_fixture.v1"
    description: str | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != "replay_fixture.v1":
            raise ReplayFixtureValidationError("schema_version must be 'replay_fixture.v1'.")
        if not self.fixture_id.strip() or not self.name.strip():
            raise ReplayFixtureValidationError("fixture_id and name must be non-empty.")
        if not isinstance(self.snapshot, MarketSnapshotV1):
            raise ReplayFixtureValidationError("snapshot must be a MarketSnapshotV1.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fixture_id": self.fixture_id,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "snapshot": self.snapshot.to_dict(),
            "expectations": self.expectations.to_dict(),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReplayFixtureV1":
        if not isinstance(payload, Mapping):
            raise ReplayFixtureValidationError("Replay fixture must be a JSON object.")
        return cls(
            schema_version=str(payload.get("schema_version", "")),
            fixture_id=str(payload.get("fixture_id", "")),
            name=str(payload.get("name", "")),
            description=_optional_string(payload.get("description")),
            tags=_required_strings(payload.get("tags", ()), "tags"),
            snapshot=MarketSnapshotV1.from_dict(_required_mapping(payload.get("snapshot"), "snapshot")),
            expectations=ReplayExpectationsV1.from_dict(
                _required_mapping(payload.get("expectations"), "expectations")
            ),
            metadata=dict(_required_mapping(payload.get("metadata", {}), "metadata")),
        )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReplayFixtureValidationError("Expected a string or null.")
    return value


def _optional_bool(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise ReplayFixtureValidationError("validation_passed must be a boolean or null.")


def _optional_strings(value: Any, name: str) -> tuple[str, ...] | None:
    return None if value is None else _required_strings(value, name)


def _required_strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise ReplayFixtureValidationError(f"{name} must be an array of strings.")
    return tuple(value)


def _required_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReplayFixtureValidationError(f"{name} must be a JSON object.")
    return value


def _optional_number(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ReplayFixtureValidationError(f"{name} must be a finite number or null.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ReplayFixtureValidationError(f"{name} must be a finite number or null.") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ReplayFixtureValidationError(f"{name} must be a finite number or null.")
    return number
