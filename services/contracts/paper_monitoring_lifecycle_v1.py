"""Typed PAPER monitoring evidence and lifecycle transition contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar

from services.contracts.active_paper_position_v1 import ActivePaperPositionV1

_ACTIONS = {
    "HOLD",
    "HOLD_WITH_CAUTION",
    "TARGET_1_HIT",
    "TARGET_2_HIT",
    "TARGET_3_HIT",
    "MOVE_STOP",
    "EXIT_NOW",
    "STOP_HIT",
    "TRADE_CLOSED",
}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


def _number(value: object, name: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or not isfinite(value):
        raise ValueError(name)
    result = float(value)
    if (positive and result <= 0.0) or (not positive and result < 0.0):
        raise ValueError(name)
    return result


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class PaperMonitoringEvidenceV1:
    evidence_id: str
    position_id: str
    observed_at: datetime
    current_bid: float
    current_ask: float
    current_last: float
    confidence: float
    setup_valid: bool
    safety_exit_required: bool = False
    is_stale: bool = False
    contradictions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("evidence_id", "position_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "observed_at"))
        for name in ("current_bid", "current_ask", "current_last"):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=True))
        if self.current_bid > self.current_ask:
            raise ValueError("current_bid exceeds current_ask")
        confidence = _number(self.confidence, "confidence")
        if confidence > 1.0:
            raise ValueError("confidence")
        object.__setattr__(self, "confidence", confidence)
        for name in ("setup_valid", "safety_exit_required", "is_stale"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)
        object.__setattr__(self, "contradictions", _messages(self.contradictions, "contradictions"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))


@dataclass(frozen=True, slots=True)
class PaperLifecycleTransitionV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_lifecycle_transition.v1"

    transition_id: str
    position_id: str
    evidence_id: str
    evaluated_at: datetime
    action: str
    previous_state: str
    next_state: str
    exit_quantity: int
    remaining_quantity: int
    effective_stop_loss: float
    reasons: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("transition_id", "position_id", "evidence_id", "previous_state", "next_state"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        action = _text(self.action, "action").upper()
        if action not in _ACTIONS:
            raise ValueError("action")
        object.__setattr__(self, "action", action)
        for name in ("exit_quantity", "remaining_quantity"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(name)
        object.__setattr__(
            self,
            "effective_stop_loss",
            _number(self.effective_stop_loss, "effective_stop_loss", positive=True),
        )
        object.__setattr__(self, "reasons", _messages(self.reasons, "reasons"))
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        if not self.reasons:
            raise ValueError("reasons")
        if action in {"TARGET_1_HIT", "TARGET_2_HIT", "TARGET_3_HIT", "EXIT_NOW", "STOP_HIT", "TRADE_CLOSED"}:
            if self.exit_quantity <= 0:
                raise ValueError("exit_quantity")
        elif self.exit_quantity != 0:
            raise ValueError("non-exit action quantity")
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only transition")
