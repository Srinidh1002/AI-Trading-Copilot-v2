"""Canonical option-chain metric contract.

This module contains no provider, broker, network, cache, decision, risk,
ranking, or execution behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, ClassVar


_ALLOWED_METRIC_STATUSES = frozenset(
    {
        "VALID",
        "VALID_WITH_WARNINGS",
        "INSUFFICIENT_DATA",
        "UNAVAILABLE",
        "MALFORMED",
        "FAILED",
    }
)

_ALLOWED_METRIC_SIGNALS = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "HIGH",
        "LOW",
        "RISING",
        "FALLING",
        "BALANCED",
        "CONCENTRATED",
        "DISPERSED",
        "NONE",
        "UNAVAILABLE",
    }
)

_BLOCKING_METRIC_STATUSES = frozenset(
    {
        "INSUFFICIENT_DATA",
        "UNAVAILABLE",
        "MALFORMED",
        "FAILED",
    }
)

_DIRECTIONAL_SIGNALS = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
    }
)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")

    return normalized


def _require_string_tuple(
    value: Any,
    field_name: str,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(f"{field_name} must be a tuple")

    normalized: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"{field_name} must contain only strings")

        clean_item = item.strip()
        if not clean_item:
            raise ValueError(
                f"{field_name} must not contain empty strings"
            )

        if clean_item in seen:
            raise ValueError(
                f"{field_name} must not contain duplicate values"
            )

        seen.add(clean_item)
        normalized.append(clean_item)

    return tuple(normalized)


def _require_parameter_tuple(
    value: Any,
) -> tuple[tuple[str, float | int | str], ...]:
    if not isinstance(value, tuple):
        raise TypeError("parameters must be a tuple")

    normalized: list[tuple[str, float | int | str]] = []
    seen_keys: set[str] = set()

    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError(
                "each parameters item must be a two-item tuple"
            )

        raw_key, raw_value = item
        key = _require_non_empty_string(raw_key, "parameter key")

        if key in seen_keys:
            raise ValueError("parameter keys must be unique")

        if isinstance(raw_value, bool):
            raise TypeError(
                "parameter values must not use booleans as numbers"
            )

        if isinstance(raw_value, float) and not isfinite(raw_value):
            raise ValueError(
                "floating-point parameter values must be finite"
            )

        if not isinstance(raw_value, (str, int, float)):
            raise TypeError(
                "parameter values must be strings, integers, or floats"
            )

        if isinstance(raw_value, str):
            raw_value = _require_non_empty_string(
                raw_value,
                f"parameter {key}",
            )

        seen_keys.add(key)
        normalized.append((key, raw_value))

    return tuple(normalized)


def _require_optional_finite_float(
    value: Any,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite number or None")

    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")

    return normalized


@dataclass(frozen=True, slots=True)
class OptionChainMetricV1:
    """One immutable canonical option-chain intelligence measurement."""

    SCHEMA_VERSION: ClassVar[str] = "option_chain_metric.v1"
    EXECUTION_MODE: ClassVar[str] = "PAPER"
    LIVE_EXECUTION_ELIGIBLE: ClassVar[bool] = False

    metric_name: str
    value: float | None
    signal: str
    status: str
    sample_size: int
    parameters: tuple[tuple[str, float | int | str], ...] = ()
    supporting_strikes: tuple[float, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        metric_name = _require_non_empty_string(
            self.metric_name,
            "metric_name",
        )
        object.__setattr__(self, "metric_name", metric_name)

        value = _require_optional_finite_float(
            self.value,
            "value",
        )
        object.__setattr__(self, "value", value)

        signal = _require_non_empty_string(
            self.signal,
            "signal",
        ).upper()
        if signal not in _ALLOWED_METRIC_SIGNALS:
            raise ValueError(
                f"unsupported option-chain metric signal: {signal}"
            )
        object.__setattr__(self, "signal", signal)

        status = _require_non_empty_string(
            self.status,
            "status",
        ).upper()
        if status not in _ALLOWED_METRIC_STATUSES:
            raise ValueError(
                f"unsupported option-chain metric status: {status}"
            )
        object.__setattr__(self, "status", status)

        if isinstance(self.sample_size, bool) or not isinstance(
            self.sample_size,
            int,
        ):
            raise TypeError("sample_size must be an integer")

        if self.sample_size < 0:
            raise ValueError("sample_size must be non-negative")

        parameters = _require_parameter_tuple(self.parameters)
        object.__setattr__(self, "parameters", parameters)

        if not isinstance(self.supporting_strikes, tuple):
            raise TypeError("supporting_strikes must be a tuple")

        normalized_strikes: list[float] = []
        seen_strikes: set[float] = set()

        for strike in self.supporting_strikes:
            if isinstance(strike, bool) or not isinstance(
                strike,
                (int, float),
            ):
                raise TypeError(
                    "supporting_strikes must contain finite numbers"
                )

            normalized_strike = float(strike)

            if not isfinite(normalized_strike):
                raise ValueError(
                    "supporting_strikes must contain finite values"
                )

            if normalized_strike <= 0.0:
                raise ValueError(
                    "supporting_strikes must contain positive values"
                )

            if normalized_strike in seen_strikes:
                raise ValueError(
                    "supporting_strikes must not contain duplicates"
                )

            seen_strikes.add(normalized_strike)
            normalized_strikes.append(normalized_strike)

        if tuple(normalized_strikes) != tuple(sorted(normalized_strikes)):
            raise ValueError(
                "supporting_strikes must be strictly ascending"
            )

        object.__setattr__(
            self,
            "supporting_strikes",
            tuple(normalized_strikes),
        )

        blockers = _require_string_tuple(
            self.blockers,
            "blockers",
        )
        warnings = _require_string_tuple(
            self.warnings,
            "warnings",
        )

        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "warnings", warnings)

        if status == "VALID":
            if blockers:
                raise ValueError("VALID metrics must not contain blockers")

            if warnings:
                raise ValueError(
                    "VALID metrics must not contain warnings"
                )

            if value is None:
                raise ValueError("VALID metrics require a numeric value")

            if signal == "UNAVAILABLE":
                raise ValueError(
                    "VALID metrics must not use UNAVAILABLE signal"
                )

        if status == "VALID_WITH_WARNINGS":
            if blockers:
                raise ValueError(
                    "VALID_WITH_WARNINGS metrics must not contain blockers"
                )

            if not warnings:
                raise ValueError(
                    "VALID_WITH_WARNINGS metrics require warnings"
                )

            if value is None:
                raise ValueError(
                    "VALID_WITH_WARNINGS metrics require a numeric value"
                )

            if signal == "UNAVAILABLE":
                raise ValueError(
                    "VALID_WITH_WARNINGS metrics must not use "
                    "UNAVAILABLE signal"
                )

        if status in _BLOCKING_METRIC_STATUSES:
            if not blockers:
                raise ValueError(
                    f"{status} metrics require at least one blocker"
                )

            if value is not None:
                raise ValueError(
                    f"{status} metrics must not fabricate a numeric value"
                )

            if signal != "UNAVAILABLE":
                raise ValueError(
                    f"{status} metrics must use UNAVAILABLE signal"
                )

        if value is None and status not in _BLOCKING_METRIC_STATUSES:
            raise ValueError(
                "a metric without a value must use a blocking status"
            )

        if status in _BLOCKING_METRIC_STATUSES and self.sample_size > 0:
            # A blocked metric may have inspected records, but it must not
            # claim a valid directional result.
            if signal in _DIRECTIONAL_SIGNALS:
                raise ValueError(
                    "blocked metrics must not expose directional signals"
                )

    @property
    def schema_version(self) -> str:
        return self.SCHEMA_VERSION

    @property
    def execution_mode(self) -> str:
        return self.EXECUTION_MODE

    @property
    def live_execution_eligible(self) -> bool:
        return self.LIVE_EXECUTION_ELIGIBLE

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic primitive-only serialization."""

        return {
            "schema_version": self.schema_version,
            "metric_name": self.metric_name,
            "value": self.value,
            "signal": self.signal,
            "status": self.status,
            "sample_size": self.sample_size,
            "parameters": [
                [key, value]
                for key, value in self.parameters
            ],
            "supporting_strikes": list(self.supporting_strikes),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
        }


__all__ = [
    "OptionChainMetricV1",
]