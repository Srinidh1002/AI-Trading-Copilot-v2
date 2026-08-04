"""Immutable daily portfolio lock state for P8."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any


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


def _reasons(value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError("lock_reason_codes must be an exact tuple")
    result: list[str] = []
    for item in value:
        item = _text(item, "lock_reason_codes")
        if item not in result:
            result.append(item)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class PaperPortfolioLockStateV1:
    trading_day_id: str
    loss_locked: bool
    profit_locked: bool
    lock_reason_codes: tuple[str, ...]
    daily_total_pnl: float
    daily_realized_net_pnl: float
    daily_loss_amount: float
    intraday_peak_equity: float
    daily_drawdown_amount: float
    evaluated_at: datetime
    loss_locked_at: datetime | None = None
    profit_locked_at: datetime | None = None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "trading_day_id", _text(self.trading_day_id, "trading_day_id"))
        if type(self.loss_locked) is not bool or type(self.profit_locked) is not bool:
            raise TypeError("lock flags must be bools")
        object.__setattr__(self, "lock_reason_codes", _reasons(self.lock_reason_codes))
        for name in ("daily_total_pnl", "daily_realized_net_pnl"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        for name in ("daily_loss_amount", "intraday_peak_equity", "daily_drawdown_amount"):
            object.__setattr__(self, name, _number(getattr(self, name), name, nonnegative=True))

        expected_loss = max(0.0, -self.daily_total_pnl)
        if not math.isclose(self.daily_loss_amount, expected_loss, abs_tol=1e-9):
            raise ValueError("daily_loss_amount mismatch")

        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        for name in ("loss_locked_at", "profit_locked_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _aware(value, name))

        if self.loss_locked and self.loss_locked_at is None:
            raise ValueError("loss_locked requires loss_locked_at")
        if not self.loss_locked and self.loss_locked_at is not None:
            raise ValueError("unlocked loss state cannot have loss_locked_at")
        if self.profit_locked and self.profit_locked_at is None:
            raise ValueError("profit_locked requires profit_locked_at")
        if not self.profit_locked and self.profit_locked_at is not None:
            raise ValueError("unlocked profit state cannot have profit_locked_at")
        if (self.loss_locked or self.profit_locked) and not self.lock_reason_codes:
            raise ValueError("locked state requires reason codes")
        if not self.loss_locked and not self.profit_locked and self.lock_reason_codes:
            raise ValueError("unlocked state cannot contain lock reasons")

        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only lock state required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    @property
    def admission_locked(self) -> bool:
        return self.loss_locked or self.profit_locked

    def to_dict(self) -> dict[str, Any]:
        return {
            "trading_day_id": self.trading_day_id,
            "loss_locked": self.loss_locked,
            "profit_locked": self.profit_locked,
            "lock_reason_codes": list(self.lock_reason_codes),
            "daily_total_pnl": self.daily_total_pnl,
            "daily_realized_net_pnl": self.daily_realized_net_pnl,
            "daily_loss_amount": self.daily_loss_amount,
            "intraday_peak_equity": self.intraday_peak_equity,
            "daily_drawdown_amount": self.daily_drawdown_amount,
            "evaluated_at": self.evaluated_at.isoformat(),
            "loss_locked_at": None if self.loss_locked_at is None else self.loss_locked_at.isoformat(),
            "profit_locked_at": None if self.profit_locked_at is None else self.profit_locked_at.isoformat(),
            "execution_mode": self.execution_mode,
            "live_execution_eligible": self.live_execution_eligible,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
