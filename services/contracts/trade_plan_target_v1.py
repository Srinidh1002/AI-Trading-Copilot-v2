"""Immutable one-target intent for a PAPER-mode trade plan."""
from __future__ import annotations
import json, math
from dataclasses import dataclass

_ROLES = {1: "RISK_REDUCTION", 2: "PRIMARY", 3: "EXTENDED"}

def _positive(value, name, *, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or (maximum is not None and value > maximum):
        raise ValueError(name)
    return float(value)

@dataclass(frozen=True, slots=True)
class TradePlanTargetV1:
    target_number: int
    target_price: float
    allocation_fraction: float
    reward_amount_per_unit: float
    reward_to_risk: float
    target_role: str
    schema_version: str = "1.0"

    def __post_init__(self):
        if type(self.target_number) is not int or self.target_number not in _ROLES:
            raise ValueError("target_number")
        role = self.target_role.strip().upper() if type(self.target_role) is str else ""
        if role != _ROLES[self.target_number]:
            raise ValueError("target_role")
        object.__setattr__(self, "target_role", role)
        object.__setattr__(self, "target_price", _positive(self.target_price, "target_price"))
        object.__setattr__(self, "allocation_fraction", _positive(self.allocation_fraction, "allocation_fraction", maximum=1))
        object.__setattr__(self, "reward_amount_per_unit", _positive(self.reward_amount_per_unit, "reward_amount_per_unit"))
        object.__setattr__(self, "reward_to_risk", _positive(self.reward_to_risk, "reward_to_risk"))
        if self.schema_version != "1.0":
            raise ValueError("schema_version")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    def semantic_dict(self):
        return self.to_dict()
