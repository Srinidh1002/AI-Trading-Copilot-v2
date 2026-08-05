"""Immutable reconciliation between prediction and PAPER lifecycle truth."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import ClassVar


_STATUSES = {
    "RECONCILED",
    "PENDING",
    "DATA_UNAVAILABLE",
    "BLOCKED",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


def _optional_text(
    value: object,
    name: str,
) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _optional_bool(
    value: object,
    name: str,
) -> bool | None:
    if value is not None and type(value) is not bool:
        raise TypeError(name)
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
class PredictionLifecycleReconciliationResultV1:
    """One deterministic reconciliation result."""

    SCHEMA_VERSION: ClassVar[str] = (
        "prediction_lifecycle_reconciliation_result.v1"
    )

    reconciliation_id: str
    prediction_id: str
    lifecycle_outcome_id: str
    position_id: str | None
    underlying_symbol: str
    exchange: str
    predicted_action: str
    lifecycle_outcome: str
    position_lifecycle_state: str | None
    reconciled_at: datetime
    status: str
    reconciliation_complete: bool
    counting_eligible: bool
    identity_matches: bool
    entry_matches: bool | None
    terminal_matches: bool | None
    fill_sequence_matches: bool | None
    quantity_matches: bool | None
    pnl_matches: bool | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "reconciliation_id",
            "prediction_id",
            "lifecycle_outcome_id",
            "underlying_symbol",
            "exchange",
            "predicted_action",
            "lifecycle_outcome",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        object.__setattr__(
            self,
            "position_id",
            _optional_text(self.position_id, "position_id"),
        )
        object.__setattr__(
            self,
            "position_lifecycle_state",
            _optional_text(
                self.position_lifecycle_state,
                "position_lifecycle_state",
            ),
        )

        status = _text(self.status, "status").upper()
        if status not in _STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "reconciled_at",
            _aware(self.reconciled_at, "reconciled_at"),
        )

        for name in (
            "reconciliation_complete",
            "counting_eligible",
            "identity_matches",
            "live_execution_eligible",
            "broker_order_submission",
            "read_only",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        for name in (
            "entry_matches",
            "terminal_matches",
            "fill_sequence_matches",
            "quantity_matches",
            "pnl_matches",
        ):
            object.__setattr__(
                self,
                name,
                _optional_bool(getattr(self, name), name),
            )

        object.__setattr__(
            self,
            "blockers",
            _messages(self.blockers, "blockers"),
        )
        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )

        if status == "RECONCILED":
            if (
                not self.reconciliation_complete
                or not self.counting_eligible
                or self.blockers
                or not self.identity_matches
            ):
                raise ValueError("RECONCILED coherence")
        elif status == "PENDING":
            if (
                self.reconciliation_complete
                or self.counting_eligible
                or not self.blockers
            ):
                raise ValueError("PENDING coherence")
        elif status == "DATA_UNAVAILABLE":
            if (
                self.reconciliation_complete
                or self.counting_eligible
                or not self.blockers
            ):
                raise ValueError("DATA_UNAVAILABLE coherence")
        else:
            if (
                self.reconciliation_complete
                or self.counting_eligible
                or not self.blockers
            ):
                raise ValueError("BLOCKED coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "PAPER-only read-only reconciliation result"
            )

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["reconciled_at"] = self.reconciled_at.isoformat()
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
        return hashlib.sha256(
            self.to_json().encode("utf-8")
        ).hexdigest()
