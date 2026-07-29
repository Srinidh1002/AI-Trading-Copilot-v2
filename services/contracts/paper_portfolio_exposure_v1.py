"""Deterministic portfolio exposure evidence for P8."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _bucket(value: object, name: str) -> Mapping[str, float]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, float] = {}
    for key, amount in value.items():
        if type(key) is not str or not key.strip():
            raise ValueError(f"{name} keys must be nonblank strings")
        if type(amount) not in (int, float) or isinstance(amount, bool):
            raise TypeError(f"{name} values must be numbers")
        numeric = float(amount)
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(f"{name} values must be finite and nonnegative")
        if key.strip() in result:
            raise ValueError(f"duplicate {name} key")
        result[key.strip()] = numeric
    return MappingProxyType(dict(sorted(result.items())))


def _warnings(value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError("warnings must be an exact tuple")
    result: list[str] = []
    for item in value:
        if type(item) is not str or not item.strip():
            raise ValueError("warnings entries must be nonblank strings")
        item = item.strip()
        if item not in result:
            result.append(item)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class PaperPortfolioExposureV1:
    instrument_risk: Mapping[str, float]
    direction_risk: Mapping[str, float]
    expiry_risk: Mapping[str, float]
    correlated_index_direction_risk: Mapping[str, float]
    total_instrument_risk: float
    total_direction_risk: float
    total_expiry_risk: float
    total_correlated_index_direction_risk: float
    metric: str = "REMAINING_RISK"
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "instrument_risk", "direction_risk", "expiry_risk",
            "correlated_index_direction_risk",
        ):
            object.__setattr__(self, name, _bucket(getattr(self, name), name))

        for field_name, bucket_name in (
            ("total_instrument_risk", "instrument_risk"),
            ("total_direction_risk", "direction_risk"),
            ("total_expiry_risk", "expiry_risk"),
            ("total_correlated_index_direction_risk", "correlated_index_direction_risk"),
        ):
            value = getattr(self, field_name)
            if type(value) not in (int, float) or isinstance(value, bool):
                raise TypeError(f"{field_name} must be a number")
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{field_name} must be finite and nonnegative")
            expected = math.fsum(getattr(self, bucket_name).values())
            if not math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(f"{field_name} does not match {bucket_name}")
            object.__setattr__(self, field_name, value)

        object.__setattr__(self, "warnings", _warnings(self.warnings))
        if self.metric != "REMAINING_RISK":
            raise ValueError("metric must be REMAINING_RISK")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only exposure required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    @classmethod
    def empty(cls) -> "PaperPortfolioExposureV1":
        return cls({}, {}, {}, {}, 0.0, 0.0, 0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_risk": dict(self.instrument_risk),
            "direction_risk": dict(self.direction_risk),
            "expiry_risk": dict(self.expiry_risk),
            "correlated_index_direction_risk": dict(self.correlated_index_direction_risk),
            "total_instrument_risk": self.total_instrument_risk,
            "total_direction_risk": self.total_direction_risk,
            "total_expiry_risk": self.total_expiry_risk,
            "total_correlated_index_direction_risk": self.total_correlated_index_direction_risk,
            "metric": self.metric,
            "warnings": list(self.warnings),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
