"""Detached P8 projection of authoritative P7 position evidence."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

_ACTIVE = frozenset({"OPEN", "PARTIALLY_EXITED"})
_TERMINAL = frozenset({
    "CLOSED_TARGET_1", "CLOSED_TARGET_2", "CLOSED_TARGET_3", "CLOSED_STOP",
    "CLOSED_INVALIDATED", "CLOSED_SESSION", "CLOSED_EXPIRY", "CANCELLED", "BLOCKED",
})


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _number(value: object, name: str, *, nonnegative: bool = False) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if nonnegative and result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def _integer(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(f"{name} must be an exact int")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


@dataclass(frozen=True, slots=True)
class PaperPortfolioPositionReferenceV1:
    portfolio_id: str
    reservation_id: str
    position_id: str
    trade_plan_id: str
    integrated_trade_plan_result_id: str
    selected_option_contract_id: str
    underlying_symbol: str
    exchange: str
    option_symbol: str
    option_type: str
    economic_direction: str
    expiry: str
    lifecycle_state: str
    transition_sequence: int
    initial_lot_count: int
    remaining_lot_count: int
    lot_size: int
    initial_quantity: int
    remaining_quantity: int
    initial_capital_amount: float
    remaining_capital_amount: float
    initial_risk_amount: float
    remaining_risk_amount: float
    realized_net_pnl: float
    unrealized_pnl: float
    total_pnl: float
    exit_fill_ids: tuple[str, ...]
    updated_at: datetime
    last_observation_id: str | None = None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "portfolio_id", "reservation_id", "position_id", "trade_plan_id",
            "integrated_trade_plan_result_id", "selected_option_contract_id",
            "underlying_symbol", "exchange", "option_symbol", "expiry",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.option_type not in {"CALL", "PUT"}:
            raise ValueError("option_type must be CALL or PUT")
        if self.economic_direction not in {"BULLISH", "BEARISH"}:
            raise ValueError("economic_direction must be BULLISH or BEARISH")
        if self.lifecycle_state not in _ACTIVE | _TERMINAL:
            raise ValueError("unsupported lifecycle_state")

        for name in (
            "transition_sequence", "initial_lot_count", "remaining_lot_count",
            "lot_size", "initial_quantity", "remaining_quantity",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), name))
        if self.initial_lot_count <= 0 or self.lot_size <= 0 or self.initial_quantity <= 0:
            raise ValueError("initial lot and quantity values must be positive")
        if self.initial_quantity != self.initial_lot_count * self.lot_size:
            raise ValueError("initial quantity mismatch")
        if self.remaining_quantity != self.remaining_lot_count * self.lot_size:
            raise ValueError("remaining quantity mismatch")
        if self.remaining_quantity > self.initial_quantity:
            raise ValueError("remaining quantity cannot exceed initial quantity")

        for name in (
            "initial_capital_amount", "remaining_capital_amount",
            "initial_risk_amount", "remaining_risk_amount",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name, nonnegative=True))
        if self.initial_capital_amount <= 0:
            raise ValueError("initial_capital_amount must be positive")
        if self.remaining_capital_amount > self.initial_capital_amount + 1e-9:
            raise ValueError("remaining capital cannot exceed initial")
        if self.remaining_risk_amount > self.initial_risk_amount + 1e-9:
            raise ValueError("remaining risk cannot exceed initial")

        for name in ("realized_net_pnl", "unrealized_pnl", "total_pnl"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if not math.isclose(self.total_pnl, self.realized_net_pnl + self.unrealized_pnl, abs_tol=1e-9):
            raise ValueError("position P&L mismatch")

        ids = tuple(_text(item, "exit_fill_ids") for item in self.exit_fill_ids)
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate exit fill ID")
        object.__setattr__(self, "exit_fill_ids", ids)
        if self.last_observation_id is not None:
            object.__setattr__(self, "last_observation_id", _text(self.last_observation_id, "last_observation_id"))
        object.__setattr__(self, "updated_at", _aware(self.updated_at, "updated_at"))

        if self.lifecycle_state in _ACTIVE:
            if self.remaining_quantity <= 0 or self.remaining_capital_amount <= 0:
                raise ValueError("active reference requires remaining quantity and capital")
        else:
            if self.remaining_quantity != 0 or self.remaining_capital_amount != 0.0 or self.remaining_risk_amount != 0.0:
                raise ValueError("terminal reference requires zero remaining quantity/capital/risk")
            if self.unrealized_pnl != 0.0 or not math.isclose(self.total_pnl, self.realized_net_pnl, abs_tol=1e-9):
                raise ValueError("terminal reference P&L mismatch")

        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only position reference required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    @property
    def is_terminal(self) -> bool:
        return self.lifecycle_state in _TERMINAL

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["exit_fill_ids"] = list(self.exit_fill_ids)
        result["updated_at"] = self.updated_at.isoformat()
        return result

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        result.pop("updated_at")
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
