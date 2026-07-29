"""Immutable PAPER-only portfolio policy for P8."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _number(value: object, name: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if positive and result <= 0:
        raise ValueError(f"{name} must be positive")
    if not positive and result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _fraction(value: object, name: str) -> float:
    result = _number(value, name, positive=True)
    if result > 1:
        raise ValueError(f"{name} must not exceed 1")
    return result


def _freeze(value: object) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("metadata must be JSON-safe")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            frozen[_text(key, "metadata key")] = _freeze(item)
        return MappingProxyType(dict(sorted(frozen.items())))
    if type(value) in (tuple, list):
        return tuple(_freeze(item) for item in value)
    raise ValueError("metadata must be JSON-safe")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class PaperPortfolioPolicyV1:
    portfolio_policy_id: str
    policy_timestamp: datetime
    maximum_concurrent_trades: int
    maximum_total_deployed_capital: float
    maximum_total_portfolio_risk_amount: float
    maximum_daily_loss_amount: float
    maximum_daily_drawdown_amount: float
    maximum_instrument_risk_fraction: float
    maximum_direction_risk_fraction: float
    maximum_correlated_index_risk_fraction: float
    maximum_expiry_risk_fraction: float
    minimum_available_cash_reserve: float = 0.0
    loss_lock_enabled: bool = True
    profit_lock_enabled: bool = False
    minimum_daily_realized_profit_to_lock: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "portfolio_policy_id", _text(self.portfolio_policy_id, "portfolio_policy_id"))
        object.__setattr__(self, "policy_timestamp", _aware(self.policy_timestamp, "policy_timestamp"))

        if type(self.maximum_concurrent_trades) is not int or isinstance(self.maximum_concurrent_trades, bool):
            raise TypeError("maximum_concurrent_trades must be an exact int")
        if self.maximum_concurrent_trades <= 0:
            raise ValueError("maximum_concurrent_trades must be positive")

        for name in (
            "maximum_total_deployed_capital",
            "maximum_total_portfolio_risk_amount",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=True))
        for name in (
            "maximum_daily_loss_amount",
            "maximum_daily_drawdown_amount",
            "minimum_available_cash_reserve",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        for name in (
            "maximum_instrument_risk_fraction",
            "maximum_direction_risk_fraction",
            "maximum_correlated_index_risk_fraction",
            "maximum_expiry_risk_fraction",
        ):
            object.__setattr__(self, name, _fraction(getattr(self, name), name))

        if type(self.loss_lock_enabled) is not bool:
            raise TypeError("loss_lock_enabled must be a bool")
        if type(self.profit_lock_enabled) is not bool:
            raise TypeError("profit_lock_enabled must be a bool")

        if self.profit_lock_enabled:
            if self.minimum_daily_realized_profit_to_lock is None:
                raise ValueError("enabled profit lock requires a threshold")
            object.__setattr__(
                self,
                "minimum_daily_realized_profit_to_lock",
                _number(
                    self.minimum_daily_realized_profit_to_lock,
                    "minimum_daily_realized_profit_to_lock",
                    positive=True,
                ),
            )
        elif self.minimum_daily_realized_profit_to_lock is not None:
            raise ValueError("disabled profit lock requires a null threshold")

        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible is not False:
            raise ValueError("live_execution_eligible must be False")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["policy_timestamp"] = self.policy_timestamp.isoformat()
        result["metadata"] = _plain(self.metadata)
        return result

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("policy_timestamp")
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
