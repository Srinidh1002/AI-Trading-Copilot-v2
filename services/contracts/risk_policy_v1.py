"""Immutable P3-5A risk-policy contract; it performs no sizing calculation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping


_BEHAVIORS = {"BLOCK", "ZERO_SIZE"}


def _positive(value: Any, name: str, *, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite and positive.")
    number = float(value)
    if not math.isfinite(number) or number <= 0 or (maximum is not None and number > maximum):
        raise ValueError(f"{name} must be finite and positive.")
    return number


def _fraction(value: Any, name: str) -> float:
    return _positive(value, name, maximum=1.0)


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


@dataclass(frozen=True, slots=True)
class RiskPolicyV1:
    policy_id: str
    policy_name: str
    capital_base: float
    maximum_capital_per_trade: float
    maximum_capital_fraction: float
    maximum_risk_per_trade: float
    maximum_risk_fraction: float
    minimum_reward_risk_ratio: float
    maximum_lots: int
    maximum_quantity: int
    allow_fractional_lots: bool
    require_stop_loss: bool
    require_target: bool
    require_positive_entry: bool
    require_positive_stop_loss: bool
    require_positive_target: bool
    require_stop_below_entry_for_long: bool
    require_target_above_entry_for_long: bool
    insufficient_capital_behavior: str
    schema_version: str = "risk_policy.v1"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != "risk_policy.v1":
            raise ValueError("Unsupported risk-policy schema.")
        for name in ("policy_id", "policy_name"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} is required.")
        capital_base = _positive(self.capital_base, "capital_base")
        object.__setattr__(self, "capital_base", capital_base)
        for name in ("maximum_capital_per_trade", "maximum_risk_per_trade"):
            object.__setattr__(self, name, _positive(getattr(self, name), name, maximum=capital_base))
        for name in ("maximum_capital_fraction", "maximum_risk_fraction"):
            object.__setattr__(self, name, _fraction(getattr(self, name), name))
        object.__setattr__(self, "minimum_reward_risk_ratio", _positive(self.minimum_reward_risk_ratio, "minimum_reward_risk_ratio"))
        for name in ("maximum_lots", "maximum_quantity"):
            object.__setattr__(self, name, _positive_int(getattr(self, name), name))
        for name in ("allow_fractional_lots", "require_stop_loss", "require_target", "require_positive_entry", "require_positive_stop_loss", "require_positive_target", "require_stop_below_entry_for_long", "require_target_above_entry_for_long"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean.")
        if self.allow_fractional_lots:
            raise ValueError("P3-5A requires allow_fractional_lots=False.")
        if self.insufficient_capital_behavior not in _BEHAVIORS:
            raise ValueError("Unsupported insufficient-capital behavior.")
        try:
            json.dumps(self.metadata, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be safe JSON data.") from exc
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        value = {name: getattr(self, name) for name in self.__dataclass_fields__}
        value["metadata"] = dict(sorted(self.metadata.items()))
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("policy_id")
        return value
