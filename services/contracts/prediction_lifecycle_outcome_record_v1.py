"""Immutable lifecycle outcome for one retained prediction."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar


_IDENTITIES = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_ACTIONS = {"CALL", "PUT", "WAIT", "NO_TRADE"}
_STATUSES = {"RESOLVED", "UNRESOLVED", "DATA_UNAVAILABLE"}
_OUTCOMES = {
    "T1_HIT",
    "T2_HIT",
    "T3_HIT",
    "STOP_HIT",
    "EARLY_EXIT_PROFIT",
    "EARLY_EXIT_LOSS",
    "EXPIRED_WITHOUT_ENTRY",
    "INVALIDATED_BEFORE_ENTRY",
    "NO_TRADE_CORRECT",
    "NO_TRADE_MISSED_MOVE",
    "DATA_UNAVAILABLE",
    "UNRESOLVED",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _optional_aware(value: object, name: str) -> datetime | None:
    return None if value is None else _aware(value, name)


def _optional_number(
    value: object,
    name: str,
    *,
    positive: bool,
) -> float | None:
    if value is None:
        return None
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(value)
        or (value <= 0.0 if positive else value < 0.0)
    ):
        raise ValueError(name)
    return float(value)


def _messages(value: object, name: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class PredictionLifecycleOutcomeRecordV1:
    """One reproducible terminal, pending or unavailable outcome."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_lifecycle_outcome_record.v1"
    )

    outcome_id: str
    prediction_id: str
    parent_cycle_id: str
    decision_result_id: str
    window_id: str
    underlying_symbol: str
    exchange: str
    predicted_action: str
    policy_id: str
    policy_version: str
    evaluated_at: datetime
    evaluation_status: str
    outcome: str
    entry_occurred: bool
    entry_at: datetime | None
    entry_premium: float | None
    highest_target_reached: int
    terminal_event_type: str | None
    terminal_event_at: datetime | None
    terminal_option_premium: float | None
    maximum_up_move_percent: float | None
    maximum_down_move_percent: float | None
    maximum_absolute_move_percent: float | None
    evidence_observation_ids: tuple[str, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "outcome_id",
            "prediction_id",
            "parent_cycle_id",
            "decision_result_id",
            "window_id",
            "policy_id",
            "policy_version",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))

        identity = (
            _text(self.underlying_symbol, "underlying_symbol").upper(),
            _text(self.exchange, "exchange").upper(),
        )
        if identity not in _IDENTITIES:
            raise ValueError("market identity")
        object.__setattr__(self, "underlying_symbol", identity[0])
        object.__setattr__(self, "exchange", identity[1])

        action = _text(self.predicted_action, "predicted_action").upper()
        status = _text(self.evaluation_status, "evaluation_status").upper()
        outcome = _text(self.outcome, "outcome").upper()
        if action not in _ACTIONS:
            raise ValueError("predicted_action")
        if status not in _STATUSES:
            raise ValueError("evaluation_status")
        if outcome not in _OUTCOMES:
            raise ValueError("outcome")
        object.__setattr__(self, "predicted_action", action)
        object.__setattr__(self, "evaluation_status", status)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))

        if type(self.entry_occurred) is not bool:
            raise TypeError("entry_occurred")
        object.__setattr__(self, "entry_at", _optional_aware(self.entry_at, "entry_at"))
        object.__setattr__(
            self,
            "entry_premium",
            _optional_number(self.entry_premium, "entry_premium", positive=True),
        )
        if self.entry_occurred != (
            self.entry_at is not None and self.entry_premium is not None
        ):
            raise ValueError("entry coherence")

        if (
            type(self.highest_target_reached) is not int
            or isinstance(self.highest_target_reached, bool)
            or self.highest_target_reached not in {0, 1, 2, 3}
        ):
            raise ValueError("highest_target_reached")

        if self.terminal_event_type is not None:
            object.__setattr__(
                self,
                "terminal_event_type",
                _text(self.terminal_event_type, "terminal_event_type").upper(),
            )
        object.__setattr__(
            self,
            "terminal_event_at",
            _optional_aware(self.terminal_event_at, "terminal_event_at"),
        )
        if (self.terminal_event_type is None) != (self.terminal_event_at is None):
            raise ValueError("terminal event coherence")

        object.__setattr__(
            self,
            "terminal_option_premium",
            _optional_number(
                self.terminal_option_premium,
                "terminal_option_premium",
                positive=True,
            ),
        )
        for name in (
            "maximum_up_move_percent",
            "maximum_down_move_percent",
            "maximum_absolute_move_percent",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(getattr(self, name), name, positive=False),
            )

        object.__setattr__(
            self,
            "evidence_observation_ids",
            _messages(self.evidence_observation_ids, "evidence_observation_ids"),
        )
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))

        if status == "RESOLVED":
            if outcome in {"UNRESOLVED", "DATA_UNAVAILABLE"} or self.blockers:
                raise ValueError("resolved outcome coherence")
        elif status == "UNRESOLVED":
            if outcome != "UNRESOLVED" or not self.blockers:
                raise ValueError("unresolved outcome coherence")
        else:
            if outcome != "DATA_UNAVAILABLE" or not self.blockers:
                raise ValueError("data-unavailable outcome coherence")

        directional = {
            "T1_HIT",
            "T2_HIT",
            "T3_HIT",
            "STOP_HIT",
            "EARLY_EXIT_PROFIT",
            "EARLY_EXIT_LOSS",
            "EXPIRED_WITHOUT_ENTRY",
            "INVALIDATED_BEFORE_ENTRY",
            "DATA_UNAVAILABLE",
            "UNRESOLVED",
        }
        abstention = {
            "NO_TRADE_CORRECT",
            "NO_TRADE_MISSED_MOVE",
            "DATA_UNAVAILABLE",
            "UNRESOLVED",
        }
        if action in {"CALL", "PUT"} and outcome not in directional:
            raise ValueError("directional outcome vocabulary")
        if action in {"WAIT", "NO_TRADE"} and outcome not in abstention:
            raise ValueError("abstention outcome vocabulary")

        expected_target = {"T1_HIT": 1, "T2_HIT": 2, "T3_HIT": 3}.get(outcome)
        if expected_target is not None and self.highest_target_reached != expected_target:
            raise ValueError("target outcome coherence")
        if (
            outcome
            in {
                "STOP_HIT",
                "EARLY_EXIT_PROFIT",
                "EARLY_EXIT_LOSS",
                "EXPIRED_WITHOUT_ENTRY",
                "INVALIDATED_BEFORE_ENTRY",
                "NO_TRADE_CORRECT",
                "NO_TRADE_MISSED_MOVE",
            }
            and self.highest_target_reached != 0
        ):
            raise ValueError("non-target outcome cannot retain target credit")
        if action in {"WAIT", "NO_TRADE"} and self.entry_occurred:
            raise ValueError("abstention action cannot contain entry")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError("PAPER-only read-only lifecycle outcome")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        for name in ("evaluated_at", "entry_at", "terminal_event_at"):
            item = getattr(self, name)
            value[name] = item.isoformat() if item is not None else None
        value["evidence_observation_ids"] = list(self.evidence_observation_ids)
        value["blockers"] = list(self.blockers)
        value["warnings"] = list(self.warnings)
        return value

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()
