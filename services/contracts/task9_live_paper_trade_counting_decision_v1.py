"""Immutable Task 9 live PAPER trade-counting decision."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


_STATUSES = {
    "COUNTED_TRADE",
    "NO_TRADE",
    "WAIT",
    "PENDING",
    "EXCLUDED_REPLAY",
    "EXCLUDED_NON_LIVE_SOURCE",
    "EXCLUDED_RUN_MISMATCH",
    "EXCLUDED_PRE_START",
    "EXCLUDED_OUT_OF_SESSION",
    "EXCLUDED_INVALID_EVIDENCE",
    "EXCLUDED_DATA_INCIDENT",
    "EXCLUDED_PREDICTION_FAILURE",
    "EXCLUDED_UNRESOLVED",
    "EXCLUDED_RECONCILIATION",
    "EXCLUDED_NO_ENTRY",
}


def _text(value: object, name: str) -> str:
    if type(value) is not str:
        raise TypeError(name)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(name)
    return cleaned


@dataclass(frozen=True, slots=True)
class Task9LivePaperTradeCountingDecisionV1:
    """One immutable Task 9 executed-trade classification."""

    SCHEMA_VERSION: ClassVar[str] = (
        "task9_live_paper_trade_counting_decision.v1"
    )

    decision_id: str
    prediction_id: str
    market: str
    status: str

    trade_target_countable: bool
    no_trade_record: bool
    wait_record: bool
    pending: bool

    position_id: str | None
    reason_codes: tuple[str, ...]
    evaluated_at: datetime

    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    read_only: bool = True
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "decision_id",
            "prediction_id",
            "market",
            "status",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        market = self.market.upper()
        status = self.status.upper()

        if market not in {"NIFTY", "SENSEX"}:
            raise ValueError("market")
        if status not in _STATUSES:
            raise ValueError("status")

        object.__setattr__(self, "market", market)
        object.__setattr__(self, "status", status)

        if self.position_id is not None:
            object.__setattr__(
                self,
                "position_id",
                _text(self.position_id, "position_id"),
            )

        if type(self.reason_codes) is not tuple:
            raise TypeError("reason_codes")

        reasons = tuple(
            dict.fromkeys(
                _text(item, "reason_codes")
                for item in self.reason_codes
            )
        )
        object.__setattr__(self, "reason_codes", reasons)

        for name in (
            "trade_target_countable",
            "no_trade_record",
            "wait_record",
            "pending",
            "live_execution_eligible",
            "broker_order_submission",
            "read_only",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if (
            not isinstance(self.evaluated_at, datetime)
            or self.evaluated_at.tzinfo is None
            or self.evaluated_at.utcoffset() is None
        ):
            raise ValueError("evaluated_at")

        if status == "COUNTED_TRADE":
            if (
                self.trade_target_countable is not True
                or self.no_trade_record
                or self.wait_record
                or self.pending
                or self.position_id is None
                or reasons
            ):
                raise ValueError("COUNTED_TRADE coherence")
        else:
            if self.trade_target_countable:
                raise ValueError(
                    "non-trade classifications cannot increment target"
                )

        if status == "NO_TRADE":
            if (
                not self.no_trade_record
                or self.wait_record
                or self.pending
                or not reasons
            ):
                raise ValueError("NO_TRADE coherence")

        if status == "WAIT":
            if (
                self.no_trade_record
                or not self.wait_record
                or self.pending
                or not reasons
            ):
                raise ValueError("WAIT coherence")

        if status == "PENDING":
            if (
                self.no_trade_record
                or self.wait_record
                or not self.pending
                or not reasons
            ):
                raise ValueError("PENDING coherence")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
            or self.read_only is not True
            or self.schema_version != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "Task 9 counting decision must remain PAPER-only"
            )
