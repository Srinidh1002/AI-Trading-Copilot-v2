"""Immutable, provider-agnostic rules for future external market context."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from services.contracts.external_market_observation_v1 import _MAP
from services.contracts.scheduled_market_event_v1 import EVENT_CATEGORIES, SEVERITIES
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES, normalize_market_identity


CANONICAL_OBSERVATION_NAMES = frozenset(_MAP)
CONFLICTING_FII_DII_BEHAVIORS = frozenset({"CONFLICTING", "WARN"})
_SEVERITY_RANK = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "EXTREME": 4, "UNAVAILABLE": 0}


def _text(value: object, name: str, *, upper: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized.upper() if upper else normalized


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{name} must be finite")
    return normalized


def _nonnegative(value: object, name: str) -> float:
    normalized = _finite(value, name)
    if normalized < 0:
        raise ValueError(f"{name} must be non-negative")
    return normalized


def _unit(value: object, name: str) -> float:
    normalized = _finite(value, name)
    if not 0 <= normalized <= 1:
        raise ValueError(f"{name} must be between zero and one")
    return normalized


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be boolean")
    return value


def _identity_observations(value: object, name: str) -> Mapping[tuple[str, str], tuple[str, ...]]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    normalized: dict[tuple[str, str], tuple[str, ...]] = {}
    for identity, observations in value.items():
        if not isinstance(identity, tuple) or len(identity) != 2:
            raise TypeError(f"{name} identity must be a pair")
        canonical = normalize_market_identity(*identity)
        if canonical not in SUPPORTED_MARKET_IDENTITIES:
            raise ValueError(f"{name} contains an unsupported identity")
        if not isinstance(observations, tuple):
            raise TypeError(f"{name} observations must be a tuple")
        items = tuple(_text(item, f"{name} observation", upper=True) for item in observations)
        if any(item not in CANONICAL_OBSERVATION_NAMES for item in items):
            raise ValueError(f"{name} contains an unsupported observation")
        if len(items) != len(set(items)) or items != tuple(sorted(items)):
            raise ValueError(f"{name} observations must be unique and ordered")
        normalized[canonical] = items
    return MappingProxyType(dict(sorted(normalized.items())))


def _number_mapping(value: object, name: str, allowed: frozenset[str]) -> Mapping[str, float]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    normalized: dict[str, float] = {}
    for key, item in value.items():
        canonical = _text(key, f"{name} key", upper=True)
        if canonical not in allowed:
            raise ValueError(f"{name} contains an unsupported key")
        normalized[canonical] = _nonnegative(item, f"{name} value")
    if tuple(normalized) != tuple(sorted(normalized)):
        raise ValueError(f"{name} must be ordered")
    return MappingProxyType(normalized)


def _categories(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    normalized = tuple(_text(item, f"{name} item", upper=True) for item in value)
    if any(item not in EVENT_CATEGORIES for item in normalized):
        raise ValueError(f"{name} contains an unsupported event category")
    if len(normalized) != len(set(normalized)) or normalized != tuple(sorted(normalized)):
        raise ValueError(f"{name} must be unique and ordered")
    return normalized


def _metadata(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("metadata must be a mapping")
    try:
        normalized = json.loads(json.dumps(dict(value), sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be JSON-safe") from exc
    return _freeze(normalized)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _default_optional_observations() -> Mapping[tuple[str, str], tuple[str, ...]]:
    names = tuple(sorted(CANONICAL_OBSERVATION_NAMES))
    return {identity: names for identity in SUPPORTED_MARKET_IDENTITIES}


def _default_zero_event_windows() -> Mapping[str, float]:
    return {category: 0.0 for category in sorted(EVENT_CATEGORIES)}


@dataclass(frozen=True, slots=True)
class ExternalContextPolicyV1:
    policy_name: str = "INITIAL_CANONICAL_EXTERNAL_CONTEXT_POLICY"
    required_observation_names: Mapping[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)
    optional_observation_names: Mapping[tuple[str, str], tuple[str, ...]] = field(default_factory=_default_optional_observations)
    minimum_available_global_observations: int = 0
    maximum_observation_age_seconds: Mapping[str, float] = field(default_factory=lambda: {name: 900.0 for name in sorted(CANONICAL_OBSERVATION_NAMES)})
    future_timestamp_tolerance_seconds: float = 5.0
    maximum_observation_timestamp_skew_seconds: float = 300.0
    maximum_acceptable_delay_seconds: float = 900.0
    allow_delayed_optional_observations: bool = True
    block_on_delayed_required_observation: bool = True
    warn_on_missing_optional_observation: bool = True
    block_on_missing_required_observation: bool = True
    block_on_stale_required_observation: bool = True
    warn_on_stale_optional_observation: bool = True
    block_on_future_required_observation: bool = True
    minimum_directional_change_percent: float = 0.10
    strong_directional_change_percent: float = 0.75
    flat_change_tolerance_percent: float = 0.05
    minimum_global_confirmation_count: int = 1
    maximum_global_conflict_count: int = 1
    global_alignment_strength_threshold: float = 0.50
    delayed_observation_penalty: float = 0.10
    missing_optional_observation_penalty: float = 0.05
    conflicting_observation_penalty: float = 0.15
    observation_weights: Mapping[str, float] = field(default_factory=lambda: {
        "BRENT_CRUDE": 0.08, "DOW_JONES": 0.04, "DXY": 0.07, "GIFT_NIFTY": 0.25,
        "HANG_SENG": 0.05, "INDIA_10Y_YIELD": 0.10, "NASDAQ": 0.08, "NIKKEI_225": 0.08,
        "SHANGHAI_COMPOSITE": 0.03, "SP500": 0.08, "US_10Y_YIELD": 0.10, "WTI_CRUDE": 0.04,
    })
    require_institutional_flow: bool = False
    maximum_institutional_flow_age_seconds: float = 172800.0
    allow_provisional_institutional_flow: bool = True
    warn_on_provisional_institutional_flow: bool = True
    block_on_stale_institutional_flow: bool = True
    warn_on_missing_institutional_flow: bool = True
    minimum_meaningful_cash_flow_crore: float = 100.0
    minimum_meaningful_derivatives_notional_crore: float = 100.0
    minimum_meaningful_contract_count: float = 1000.0
    conflicting_fii_dii_behavior: str = "CONFLICTING"
    previous_session_flow_allowed: bool = True
    maximum_previous_session_age_days: int = 2
    institutional_flow_weight: float = 0.25
    institutional_conflict_penalty: float = 0.15
    provisional_flow_penalty: float = 0.10
    event_lead_seconds_by_category: Mapping[str, float] = field(default_factory=lambda: {
        **_default_zero_event_windows(), "CPI": 900.0, "ELECTION": 1800.0, "GDP": 900.0,
        "OTHER_SCHEDULED_MACRO": 600.0, "RBI_POLICY": 1800.0, "UNION_BUDGET": 3600.0, "WPI": 900.0,
    })
    event_cooldown_seconds_by_category: Mapping[str, float] = field(default_factory=lambda: {
        **_default_zero_event_windows(), "CPI": 600.0, "GDP": 600.0, "RBI_POLICY": 900.0,
        "UNION_BUDGET": 1800.0, "WPI": 600.0,
    })
    blocking_event_categories: tuple[str, ...] = ("CPI", "GDP", "RBI_POLICY", "UNION_BUDGET", "WPI")
    warning_event_categories: tuple[str, ...] = ("ELECTION", "MONTHLY_EXPIRY", "OTHER_SCHEDULED_MACRO", "ROLLOVER", "WEEKLY_EXPIRY")
    minimum_blocking_severity: str = "HIGH"
    minimum_warning_severity: str = "MODERATE"
    block_new_entries_for_active_events: bool = True
    allow_analysis_during_entry_block: bool = True
    block_on_tentative_extreme_events: bool = True
    warn_on_tentative_events: bool = True
    block_on_stale_event_calendar: bool = False
    warn_on_missing_event_calendar: bool = True
    maximum_event_source_age_seconds: float = 172800.0
    maximum_event_timestamp_skew_seconds: float = 300.0
    holiday_event_owned_by_session_validation: bool = True
    special_session_owned_by_session_validation: bool = True
    expiry_event_is_context_only: bool = True
    rollover_event_is_context_only: bool = True
    require_global_context: bool = False
    require_institutional_context: bool = False
    require_event_context: bool = False
    minimum_available_component_count: int = 0
    global_context_weight: float = 0.40
    institutional_context_weight: float = 0.25
    event_context_weight: float = 0.35
    missing_optional_component_penalty: float = 0.10
    component_conflict_penalty: float = 0.15
    event_block_precedence: bool = True
    fail_closed_on_invalid_mandatory_component: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "external_context_policy.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_name", _text(self.policy_name, "policy_name"))
        required = _identity_observations(self.required_observation_names, "required_observation_names")
        optional = _identity_observations(self.optional_observation_names, "optional_observation_names")
        for identity in set(required) | set(optional):
            if set(required.get(identity, ())) & set(optional.get(identity, ())):
                raise ValueError("required and optional observations must not overlap")
        object.__setattr__(self, "required_observation_names", required)
        object.__setattr__(self, "optional_observation_names", optional)
        object.__setattr__(self, "maximum_observation_age_seconds", _number_mapping(self.maximum_observation_age_seconds, "maximum_observation_age_seconds", CANONICAL_OBSERVATION_NAMES))

        if isinstance(self.maximum_previous_session_age_days, bool) or not isinstance(self.maximum_previous_session_age_days, int):
            raise TypeError("maximum_previous_session_age_days must be an integer")
        for name in (
            "future_timestamp_tolerance_seconds", "maximum_observation_timestamp_skew_seconds",
            "maximum_acceptable_delay_seconds", "minimum_directional_change_percent",
            "strong_directional_change_percent", "flat_change_tolerance_percent",
            "maximum_institutional_flow_age_seconds", "minimum_meaningful_cash_flow_crore",
            "minimum_meaningful_derivatives_notional_crore", "minimum_meaningful_contract_count",
            "maximum_event_source_age_seconds", "maximum_event_timestamp_skew_seconds",
            "maximum_previous_session_age_days",
        ):
            value = _nonnegative(getattr(self, name), name)
            if name == "maximum_previous_session_age_days":
                value = int(value)
            object.__setattr__(self, name, value)
        if not self.flat_change_tolerance_percent <= self.minimum_directional_change_percent < self.strong_directional_change_percent:
            raise ValueError("directional thresholds must be ordered")

        for name in (
            "global_alignment_strength_threshold", "delayed_observation_penalty", "missing_optional_observation_penalty",
            "conflicting_observation_penalty", "institutional_flow_weight", "institutional_conflict_penalty",
            "provisional_flow_penalty", "missing_optional_component_penalty", "component_conflict_penalty",
        ):
            object.__setattr__(self, name, _unit(getattr(self, name), name))
        weights = _number_mapping(self.observation_weights, "observation_weights", CANONICAL_OBSERVATION_NAMES)
        if not weights or any(value <= 0 or value > 1 for value in weights.values()) or not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12):
            raise ValueError("observation weights must be non-zero unit weights summing to one")
        object.__setattr__(self, "observation_weights", weights)

        for name in (
            "allow_delayed_optional_observations", "block_on_delayed_required_observation",
            "warn_on_missing_optional_observation", "block_on_missing_required_observation",
            "block_on_stale_required_observation", "warn_on_stale_optional_observation",
            "block_on_future_required_observation", "require_institutional_flow",
            "allow_provisional_institutional_flow", "warn_on_provisional_institutional_flow",
            "block_on_stale_institutional_flow", "warn_on_missing_institutional_flow",
            "previous_session_flow_allowed", "block_new_entries_for_active_events",
            "allow_analysis_during_entry_block", "block_on_tentative_extreme_events", "warn_on_tentative_events",
            "block_on_stale_event_calendar", "warn_on_missing_event_calendar",
            "holiday_event_owned_by_session_validation", "special_session_owned_by_session_validation",
            "expiry_event_is_context_only", "rollover_event_is_context_only", "require_global_context",
            "require_institutional_context", "require_event_context", "event_block_precedence",
            "fail_closed_on_invalid_mandatory_component",
        ):
            object.__setattr__(self, name, _boolean(getattr(self, name), name))

        behavior = _text(self.conflicting_fii_dii_behavior, "conflicting_fii_dii_behavior", upper=True)
        if behavior not in CONFLICTING_FII_DII_BEHAVIORS:
            raise ValueError("unsupported conflicting_fii_dii_behavior")
        object.__setattr__(self, "conflicting_fii_dii_behavior", behavior)
        lead = _number_mapping(self.event_lead_seconds_by_category, "event_lead_seconds_by_category", EVENT_CATEGORIES)
        cooldown = _number_mapping(self.event_cooldown_seconds_by_category, "event_cooldown_seconds_by_category", EVENT_CATEGORIES)
        object.__setattr__(self, "event_lead_seconds_by_category", lead)
        object.__setattr__(self, "event_cooldown_seconds_by_category", cooldown)
        blocking = _categories(self.blocking_event_categories, "blocking_event_categories")
        warning = _categories(self.warning_event_categories, "warning_event_categories")
        if set(blocking) & set(warning):
            raise ValueError("event categories cannot be both blocking and warning")
        object.__setattr__(self, "blocking_event_categories", blocking)
        object.__setattr__(self, "warning_event_categories", warning)
        for name in ("minimum_blocking_severity", "minimum_warning_severity"):
            severity = _text(getattr(self, name), name, upper=True)
            if severity not in SEVERITIES or severity == "UNAVAILABLE":
                raise ValueError(f"unsupported {name}")
            object.__setattr__(self, name, severity)
        if _SEVERITY_RANK[self.minimum_blocking_severity] < _SEVERITY_RANK[self.minimum_warning_severity]:
            raise ValueError("blocking severity must not be weaker than warning severity")

        for name in ("minimum_available_global_observations", "minimum_global_confirmation_count", "maximum_global_conflict_count", "minimum_available_component_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        possible_global = max((len(set(required.get(identity, ())) | set(optional.get(identity, ()))) for identity in set(required) | set(optional)), default=0)
        if self.minimum_available_global_observations > possible_global:
            raise ValueError("minimum global observations is not possible")
        if self.minimum_global_confirmation_count > possible_global:
            raise ValueError("minimum global confirmations is not possible")
        mandatory_count = sum((self.require_global_context, self.require_institutional_context, self.require_event_context))
        if self.minimum_available_component_count < mandatory_count or self.minimum_available_component_count > 3:
            raise ValueError("minimum component count is inconsistent with mandatory components")
        aggregate_weights = (self.global_context_weight, self.institutional_context_weight, self.event_context_weight)
        if not all(0 <= _finite(value, "component weight") <= 1 for value in aggregate_weights) or not math.isclose(sum(aggregate_weights), 1.0, abs_tol=1e-12):
            raise ValueError("aggregate component weights must sum to one")
        if not any(aggregate_weights):
            raise ValueError("aggregate component weights cannot all be zero")

        object.__setattr__(self, "metadata", _metadata(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.schema_version != "external_context_policy.v1":
            raise ValueError("external context policy is paper-only v1")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        for name in ("required_observation_names", "optional_observation_names"):
            result[name] = [[[identity[0], identity[1]], list(observations)] for identity, observations in getattr(self, name).items()]
        for name in ("maximum_observation_age_seconds", "observation_weights", "event_lead_seconds_by_category", "event_cooldown_seconds_by_category"):
            result[name] = dict(getattr(self, name))
        for name in ("blocking_event_categories", "warning_event_categories"):
            result[name] = list(getattr(self, name))
        result["metadata"] = _thaw(self.metadata)
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        return self.to_dict()


DEFAULT_EXTERNAL_CONTEXT_POLICY = ExternalContextPolicyV1()
