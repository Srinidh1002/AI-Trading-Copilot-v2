"""Immutable PAPER-only prediction record for one parent-cycle market."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar

_IDENTITIES = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "UNAVAILABLE"}
_DIRECTIONS = {"BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE", "CONFLICTING"}
_ACTIONS = {"CALL", "PUT", "WAIT"}
_ELIGIBILITY = {"ELIGIBLE", "INELIGIBLE", "UNAVAILABLE", "CONFLICTING"}
_PARENT_DECISIONS = {"SELECTED", "NO_TRADE"}
_OUTCOME_REASONS = {"SELECTED", "INELIGIBLE", "STALE", "SKEW_BLOCKED", "CHILD_FAILED", "LOWER_RANK", "TIE_BREAK_LOSS"}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
        raise ValueError(name)
    return cleaned


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name)
    return value


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _score(value: object, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or not isfinite(value) or not 0.0 <= value <= 100.0:
        raise ValueError(name)
    return float(value)


@dataclass(frozen=True, slots=True)
class PredictionRecordV1:
    SCHEMA_VERSION: ClassVar[str] = "prediction_record.v1"

    prediction_id: str
    parent_cycle_id: str
    decision_result_id: str
    child_result_id: str
    observation_id: str
    underlying_symbol: str
    exchange: str
    requested_at: datetime
    completed_at: datetime
    market_timestamp: datetime | None
    received_at: datetime
    start_underlying_price: float
    terminal_status: str
    candidate_id: str | None
    predicted_direction: str
    predicted_action: str
    eligibility: str
    confidence: float
    score: float
    rank_value: float
    eligible_for_comparison: bool
    outcome_reason: str
    parent_decision: str
    parent_selected: bool
    rationale: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("prediction_id", "parent_cycle_id", "decision_result_id", "child_result_id", "observation_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        identity = (_text(self.underlying_symbol, "underlying_symbol").upper(), _text(self.exchange, "exchange").upper())
        if identity not in _IDENTITIES:
            raise ValueError("market identity")
        object.__setattr__(self, "underlying_symbol", identity[0])
        object.__setattr__(self, "exchange", identity[1])

        requested = _aware(self.requested_at, "requested_at")
        completed = _aware(self.completed_at, "completed_at")
        received = _aware(self.received_at, "received_at")
        market = None if self.market_timestamp is None else _aware(self.market_timestamp, "market_timestamp")
        if requested > completed or requested > received or (market is not None and market > received):
            raise ValueError("timestamp ordering")

        if (
            type(self.start_underlying_price) not in (int, float)
            or isinstance(self.start_underlying_price, bool)
            or not isfinite(self.start_underlying_price)
            or self.start_underlying_price <= 0.0
        ):
            raise ValueError("start_underlying_price")
        object.__setattr__(self, "start_underlying_price", float(self.start_underlying_price))

        status = _text(self.terminal_status, "terminal_status").upper()
        direction = _text(self.predicted_direction, "predicted_direction").upper()
        action = _text(self.predicted_action, "predicted_action").upper()
        eligibility = _text(self.eligibility, "eligibility").upper()
        outcome = _text(self.outcome_reason, "outcome_reason").upper()
        decision = _text(self.parent_decision, "parent_decision").upper()
        if status not in _TERMINAL_STATUSES or direction not in _DIRECTIONS or action not in _ACTIONS or eligibility not in _ELIGIBILITY or outcome not in _OUTCOME_REASONS or decision not in _PARENT_DECISIONS:
            raise ValueError("controlled vocabulary")
        object.__setattr__(self, "terminal_status", status)
        object.__setattr__(self, "predicted_direction", direction)
        object.__setattr__(self, "predicted_action", action)
        object.__setattr__(self, "eligibility", eligibility)
        object.__setattr__(self, "outcome_reason", outcome)
        object.__setattr__(self, "parent_decision", decision)
        if self.candidate_id is not None:
            object.__setattr__(self, "candidate_id", _text(self.candidate_id, "candidate_id"))

        for name in ("confidence", "score", "rank_value"):
            object.__setattr__(self, name, _score(getattr(self, name), name))
        if type(self.eligible_for_comparison) is not bool or type(self.parent_selected) is not bool:
            raise TypeError("boolean flags")
        if action == "CALL" and direction != "BULLISH":
            raise ValueError("CALL requires BULLISH direction")
        if action == "PUT" and direction != "BEARISH":
            raise ValueError("PUT requires BEARISH direction")
        if self.parent_selected != (outcome == "SELECTED"):
            raise ValueError("parent_selected coherence")
        if decision == "NO_TRADE" and self.parent_selected:
            raise ValueError("NO_TRADE cannot select prediction")
        if action == "WAIT" and self.parent_selected:
            raise ValueError("selected prediction cannot WAIT")
        if status != "COMPLETED":
            if self.candidate_id is not None or action != "WAIT" or any(value != 0.0 for value in (self.confidence, self.score, self.rank_value)):
                raise ValueError("non-completed prediction coherence")
        if self.candidate_id is None and action != "WAIT":
            raise ValueError("action requires candidate")
        if not self.eligible_for_comparison and self.rank_value != 0.0:
            raise ValueError("ineligible comparison must use zero rank")

        for name in ("rationale", "blockers", "warnings", "errors"):
            object.__setattr__(self, name, _messages(getattr(self, name), name))
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.broker_order_submission is not False or self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("PAPER-only prediction record")

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        for name in ("requested_at", "completed_at", "received_at"):
            value[name] = getattr(self, name).isoformat()
        value["market_timestamp"] = self.market_timestamp.isoformat() if self.market_timestamp else None
        for name in ("rationale", "blockers", "warnings", "errors"):
            value[name] = list(getattr(self, name))
        return value

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)

    @property
    def semantic_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


def prediction_record_from_dict(value: object) -> PredictionRecordV1:
    if type(value) is not dict:
        raise TypeError("prediction record payload must be a dictionary")
    payload = dict(value)
    payload.pop("semantic_hash", None)
    for name in ("requested_at", "completed_at", "received_at"):
        raw = payload.get(name)
        if type(raw) is not str:
            raise ValueError(f"{name} must be an ISO datetime string")
        try:
            payload[name] = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"invalid {name}") from exc
    raw_market = payload.get("market_timestamp")
    if raw_market is not None:
        if type(raw_market) is not str:
            raise ValueError("market_timestamp must be an ISO datetime string or null")
        try:
            payload["market_timestamp"] = datetime.fromisoformat(raw_market)
        except ValueError as exc:
            raise ValueError("invalid market_timestamp") from exc
    for name in ("rationale", "blockers", "warnings", "errors"):
        raw = payload.get(name, [])
        if type(raw) is not list:
            raise ValueError(f"{name} must be a list")
        payload[name] = tuple(raw)
    return PredictionRecordV1(**payload)
