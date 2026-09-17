"""Immutable PAPER-only capital reservation contract for P8."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping

_RESERVATION_STATUSES = frozenset({"PENDING_HOLD", "ACTIVE", "RELEASED", "BLOCKED"})
_P7_ACTIVE_STATES = frozenset({"OPEN", "PARTIALLY_EXITED"})
_P7_TERMINAL_STATES = frozenset({
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


def _number(value: object, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


def _integer(value: object, name: str) -> int:
    if type(value) is not int or isinstance(value, bool):
        raise TypeError(f"{name} must be an exact int")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _diagnostics(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an exact tuple")
    result: list[str] = []
    for item in value:
        item = _text(item, name)
        if item not in result:
            result.append(item)
    return tuple(result)


def _freeze(value: object) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("metadata must be JSON-safe")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(dict(sorted((_text(k, "metadata key"), _freeze(v)) for k, v in value.items())))
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
class PaperCapitalReservationV1:
    reservation_id: str
    portfolio_id: str
    admission_request_id: str
    admission_idempotency_key: str
    integrated_trade_plan_result_id: str
    trade_plan_id: str
    reservation_status: str
    original_capital_amount: float
    remaining_capital_amount: float
    released_capital_amount: float
    original_risk_amount: float
    remaining_risk_amount: float
    initial_quantity: int
    remaining_quantity: int
    created_at: datetime
    updated_at: datetime
    position_id: str | None = None
    last_p7_lifecycle_state: str | None = None
    last_p7_transition_sequence: int = 0
    processed_fill_ids: tuple[str, ...] = ()
    activated_at: datetime | None = None
    released_at: datetime | None = None
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for name in (
            "reservation_id", "portfolio_id", "admission_request_id",
            "admission_idempotency_key", "integrated_trade_plan_result_id", "trade_plan_id",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        if self.position_id is not None:
            object.__setattr__(self, "position_id", _text(self.position_id, "position_id"))
        if self.reservation_status not in _RESERVATION_STATUSES:
            raise ValueError("unsupported reservation_status")

        for name in (
            "original_capital_amount", "remaining_capital_amount", "released_capital_amount",
            "original_risk_amount", "remaining_risk_amount",
        ):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.original_capital_amount <= 0:
            raise ValueError("original_capital_amount must be positive")
        if not math.isclose(
            self.original_capital_amount,
            self.remaining_capital_amount + self.released_capital_amount,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError("reservation capital arithmetic mismatch")
        if self.remaining_risk_amount > self.original_risk_amount + 1e-9:
            raise ValueError("remaining_risk_amount cannot exceed original_risk_amount")

        object.__setattr__(self, "initial_quantity", _integer(self.initial_quantity, "initial_quantity"))
        object.__setattr__(self, "remaining_quantity", _integer(self.remaining_quantity, "remaining_quantity"))
        if self.initial_quantity <= 0:
            raise ValueError("initial_quantity must be positive")
        if self.remaining_quantity > self.initial_quantity:
            raise ValueError("remaining_quantity cannot exceed initial_quantity")

        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _aware(self.updated_at, "updated_at"))
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        for name in ("activated_at", "released_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _aware(value, name))

        object.__setattr__(
            self,
            "last_p7_transition_sequence",
            _integer(self.last_p7_transition_sequence, "last_p7_transition_sequence"),
        )
        if self.last_p7_lifecycle_state is not None:
            object.__setattr__(
                self,
                "last_p7_lifecycle_state",
                _text(self.last_p7_lifecycle_state, "last_p7_lifecycle_state"),
            )

        object.__setattr__(
            self,
            "processed_fill_ids",
            tuple(sorted({_text(item, "processed_fill_ids") for item in self.processed_fill_ids})),
        )
        for name in ("blockers", "decision_reasons", "warnings"):
            object.__setattr__(self, name, _diagnostics(getattr(self, name), name))

        if self.reservation_status == "PENDING_HOLD":
            if self.position_id is not None or self.activated_at is not None or self.released_at is not None:
                raise ValueError("PENDING_HOLD cannot be bound or released")
            if self.remaining_quantity != self.initial_quantity:
                raise ValueError("PENDING_HOLD must retain full quantity")
            if not math.isclose(self.remaining_capital_amount, self.original_capital_amount, abs_tol=1e-9):
                raise ValueError("PENDING_HOLD must retain full capital")
            if not math.isclose(self.remaining_risk_amount, self.original_risk_amount, abs_tol=1e-9):
                raise ValueError("PENDING_HOLD must retain full risk")
        elif self.reservation_status == "ACTIVE":
            if self.position_id is None or self.activated_at is None or self.released_at is not None:
                raise ValueError("ACTIVE requires a bound position and activation time")
            if self.last_p7_lifecycle_state not in _P7_ACTIVE_STATES:
                raise ValueError("ACTIVE requires an active P7 lifecycle state")
            if self.remaining_quantity <= 0 or self.remaining_capital_amount <= 0:
                raise ValueError("ACTIVE requires remaining quantity and capital")
        elif self.reservation_status == "RELEASED":
            if self.released_at is None:
                raise ValueError("RELEASED requires released_at")
            if self.remaining_quantity != 0:
                raise ValueError("RELEASED requires zero remaining quantity")
            if self.remaining_capital_amount != 0.0 or self.remaining_risk_amount != 0.0:
                raise ValueError("RELEASED requires zero remaining capital and risk")
            if not math.isclose(self.released_capital_amount, self.original_capital_amount, abs_tol=1e-9):
                raise ValueError("RELEASED must release the full original amount")
            if self.last_p7_lifecycle_state is not None and self.last_p7_lifecycle_state not in _P7_TERMINAL_STATES:
                raise ValueError("RELEASED lifecycle state must be terminal")
        elif self.reservation_status == "BLOCKED" and not self.blockers:
            raise ValueError("BLOCKED requires blockers")

        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("PAPER-only reservation required")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        for name in ("created_at", "updated_at", "activated_at", "released_at"):
            if result[name] is not None:
                result[name] = result[name].isoformat()
        for name in ("processed_fill_ids", "blockers", "decision_reasons", "warnings"):
            result[name] = list(result[name])
        result["metadata"] = _plain(self.metadata)
        return result

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        for name in ("created_at", "updated_at", "activated_at", "released_at"):
            result.pop(name)
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
