"""Immutable result of one certification-counting decision."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar


_STATUSES = {
    "INCLUDED",
    "INCLUDED_NON_TRADE",
    "INCLUDED_WAIT",
    "PENDING_OUTCOME",
    "EXCLUDED_REPLAY",
    "EXCLUDED_BACKTEST",
    "EXCLUDED_DIAGNOSTIC",
    "EXCLUDED_FIXTURE",
    "EXCLUDED_DEVELOPMENT",
    "EXCLUDED_RUN_MISMATCH",
    "EXCLUDED_PRE_START",
    "EXCLUDED_VERSION_MISMATCH",
    "EXCLUDED_OUT_OF_SESSION",
    "EXCLUDED_INVALID_EVIDENCE",
    "EXCLUDED_CHILD_FAILURE",
    "EXCLUDED_DATA_INCIDENT",
    "EXCLUDED_DATA_UNAVAILABLE",
    "EXCLUDED_TERMINAL_PREDICTION",
    "EXCLUDED_UNEVALUABLE_OUTCOME",
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


def _messages(
    value: object,
    name: str,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)
    return tuple(
        dict.fromkeys(
            _text(item, name)
            for item in value
        )
    )


@dataclass(frozen=True, slots=True)
class PredictionCertificationCountingDecisionV1:
    """One reproducible include, pending, or exclude decision."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_certification_counting_decision.v1"
    )

    decision_id: str
    counting_key: str
    prediction_id: str
    outcome_id: str | None
    official_run_id: str
    underlying_symbol: str
    exchange: str
    predicted_action: str
    parent_decision: str
    status: str
    countable: bool
    pending: bool
    reason_codes: tuple[str, ...]
    policy_id: str
    policy_version: str
    system_version: str
    provider_version: str
    evaluated_at: datetime
    counter_reset_allowed: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "decision_id",
            "counting_key",
            "prediction_id",
            "official_run_id",
            "underlying_symbol",
            "exchange",
            "predicted_action",
            "parent_decision",
            "policy_id",
            "policy_version",
            "system_version",
            "provider_version",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        if self.outcome_id is not None:
            object.__setattr__(
                self,
                "outcome_id",
                _text(self.outcome_id, "outcome_id"),
            )

        status = _text(self.status, "status").upper()
        if status not in _STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)

        for name in (
            "countable",
            "pending",
            "counter_reset_allowed",
            "live_execution_eligible",
            "broker_order_submission",
            "read_only",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        reasons = _messages(
            self.reason_codes,
            "reason_codes",
        )
        object.__setattr__(
            self,
            "reason_codes",
            reasons,
        )

        if status == "INCLUDED":
            if (
                self.countable is not True
                or self.pending is not False
                or reasons
                or self.outcome_id is None
            ):
                raise ValueError(
                    "INCLUDED decision coherence"
                )
        elif status in {"INCLUDED_NON_TRADE", "INCLUDED_WAIT"}:
            if (
                self.countable is not False
                or self.pending is not False
                or reasons
                or self.outcome_id is None
            ):
                raise ValueError(
                    f"{status} decision coherence"
                )
        elif status == "PENDING_OUTCOME":
            if (
                self.countable is not False
                or self.pending is not True
                or not reasons
                or self.outcome_id is not None
            ):
                raise ValueError(
                    "PENDING_OUTCOME decision coherence"
                )
        else:
            if (
                self.countable is not False
                or self.pending is not False
                or not reasons
            ):
                raise ValueError(
                    "excluded decision coherence"
                )

        if len(self.counting_key) != 64:
            raise ValueError("counting_key")
        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )

        if (
            self.counter_reset_allowed is not False
            or self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "immutable PAPER-only counting decision"
            )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["evaluated_at"] = self.evaluated_at.isoformat()
        value["reason_codes"] = list(self.reason_codes)
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
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()
