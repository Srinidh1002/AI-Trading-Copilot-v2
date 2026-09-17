"""Authoritative Task 9 prediction lifecycle timing contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


POLICY_ID = "task9-prediction-lifecycle-timing.v1"
_IDENTITIES = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_ACTIONS = {"CALL", "PUT", "WAIT", "NO_TRADE"}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (result := value.strip()):
        raise ValueError(name)
    return result


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


@dataclass(frozen=True, slots=True)
class PredictionLifecycleTimingPolicyV1:
    """Fixed Task 9 lifecycle horizons; session limits are supplied separately."""
    POLICY_ID: ClassVar[str] = POLICY_ID
    policy_id: str = POLICY_ID
    entry_horizon_minutes: int = 5
    validity_horizon_minutes: int = 15
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "prediction_lifecycle_timing_policy.v1"

    def __post_init__(self) -> None:
        if self.policy_id != POLICY_ID or self.entry_horizon_minutes != 5 or self.validity_horizon_minutes != 15:
            raise ValueError("Task 9 timing policy is fixed")
        if self.execution_mode != "PAPER" or self.live_execution_eligible or self.broker_order_submission:
            raise ValueError("PAPER-only timing policy")


@dataclass(frozen=True, slots=True)
class PredictionLifecycleWindowV1:
    SCHEMA_VERSION: ClassVar[str] = "prediction_lifecycle_window.v1"
    prediction_id: str
    parent_cycle_id: str
    underlying_symbol: str
    exchange: str
    action: str
    window_starts_at: datetime
    entry_window_ends_at: datetime
    validity_window_ends_at: datetime
    policy_id: str
    provenance: str
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("prediction_id", "parent_cycle_id", "provenance"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        identity = (_text(self.underlying_symbol, "underlying_symbol").upper(), _text(self.exchange, "exchange").upper())
        if identity not in _IDENTITIES:
            raise ValueError("market identity")
        object.__setattr__(self, "underlying_symbol", identity[0]); object.__setattr__(self, "exchange", identity[1])
        action = _text(self.action, "action").upper()
        if action not in _ACTIONS or self.policy_id != POLICY_ID:
            raise ValueError("action or policy_id")
        object.__setattr__(self, "action", action)
        start = _aware(self.window_starts_at, "window_starts_at")
        entry = _aware(self.entry_window_ends_at, "entry_window_ends_at")
        validity = _aware(self.validity_window_ends_at, "validity_window_ends_at")
        if entry < start or validity < entry:
            raise ValueError("window ordering")
        if self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible or self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("PAPER-only lifecycle window")

    def to_dict(self) -> dict[str, object]:
        return {**self.__dict__} if hasattr(self, "__dict__") else {
            name: (getattr(self, name).isoformat() if name.endswith("_at") else getattr(self, name))
            for name in ("prediction_id", "parent_cycle_id", "underlying_symbol", "exchange", "action", "window_starts_at", "entry_window_ends_at", "validity_window_ends_at", "policy_id", "provenance", "execution_mode", "broker_order_submission", "live_execution_eligible", "schema_version")
        }


def prediction_lifecycle_window_from_dict(value: object) -> PredictionLifecycleWindowV1:
    if type(value) is not dict:
        raise TypeError("window payload")
    payload = dict(value)
    for name in ("window_starts_at", "entry_window_ends_at", "validity_window_ends_at"):
        try:
            payload[name] = datetime.fromisoformat(payload[name])
        except (TypeError, ValueError) as exc:
            raise ValueError(name) from exc
    return PredictionLifecycleWindowV1(**payload)
