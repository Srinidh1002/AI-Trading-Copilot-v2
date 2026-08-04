"""Typed PAPER trade closure, capital release, and journal contracts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar


_CLOSURE_REASONS = {
    "TARGET_3",
    "STOP",
    "EARLY_SAFETY_EXIT",
    "MANUAL_CERTIFIED_CLOSE",
}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not (cleaned := value.strip()):
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


def _number(
    value: object,
    name: str,
    *,
    positive: bool = False,
    allow_negative: bool = False,
) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise ValueError(name)
    result = float(value)
    if positive and result <= 0.0:
        raise ValueError(name)
    if not positive and not allow_negative and result < 0.0:
        raise ValueError(name)
    return result


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class PaperTradeClosureJournalEntryV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_trade_closure_journal_entry.v1"

    journal_entry_id: str
    closure_id: str
    position_id: str
    recommendation_id: str
    reservation_result_id: str
    fill_result_id: str
    contract: str
    underlying_symbol: str
    exchange: str
    option_right: str
    opened_at: datetime
    closed_at: datetime
    closure_reason: str
    initial_quantity: int
    closed_quantity: int
    entry_price: float
    final_exit_price: float
    realized_pnl: float
    released_capital: float
    released_risk: float
    processed_event_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "journal_entry_id",
            "closure_id",
            "position_id",
            "recommendation_id",
            "reservation_result_id",
            "fill_result_id",
            "contract",
            "underlying_symbol",
            "exchange",
            "option_right",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        object.__setattr__(
            self,
            "opened_at",
            _aware(self.opened_at, "opened_at"),
        )
        object.__setattr__(
            self,
            "closed_at",
            _aware(self.closed_at, "closed_at"),
        )
        if self.closed_at < self.opened_at:
            raise ValueError("closed_at precedes opened_at")

        reason = _text(
            self.closure_reason,
            "closure_reason",
        ).upper()
        if reason not in _CLOSURE_REASONS:
            raise ValueError("closure_reason")
        object.__setattr__(self, "closure_reason", reason)

        for name in ("initial_quantity", "closed_quantity"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(name)
        if self.closed_quantity != self.initial_quantity:
            raise ValueError("closed_quantity")

        for name in (
            "entry_price",
            "final_exit_price",
            "released_capital",
            "released_risk",
        ):
            object.__setattr__(
                self,
                name,
                _number(
                    getattr(self, name),
                    name,
                    positive=True,
                ),
            )
        object.__setattr__(
            self,
            "realized_pnl",
            _number(
                self.realized_pnl,
                "realized_pnl",
                allow_negative=True,
            ),
        )
        object.__setattr__(
            self,
            "processed_event_ids",
            _messages(
                self.processed_event_ids,
                "processed_event_ids",
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only journal entry")


@dataclass(frozen=True, slots=True)
class PaperTradeFinalizationResultV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_trade_finalization_result.v1"

    finalization_result_id: str
    closure_id: str
    position_id: str
    finalized_at: datetime
    status: str
    released_capital: float
    released_risk: float
    journal_entry: PaperTradeClosureJournalEntryV1
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "finalization_result_id",
            "closure_id",
            "position_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )
        object.__setattr__(
            self,
            "finalized_at",
            _aware(self.finalized_at, "finalized_at"),
        )
        if self.status != "FINALIZED":
            raise ValueError("status")
        for name in ("released_capital", "released_risk"):
            object.__setattr__(
                self,
                name,
                _number(
                    getattr(self, name),
                    name,
                    positive=True,
                ),
            )
        if type(self.journal_entry) is not PaperTradeClosureJournalEntryV1:
            raise TypeError("journal_entry")
        if self.journal_entry.closure_id != self.closure_id:
            raise ValueError("closure_id mismatch")
        if self.journal_entry.position_id != self.position_id:
            raise ValueError("position_id mismatch")
        if self.journal_entry.released_capital != self.released_capital:
            raise ValueError("released_capital mismatch")
        if self.journal_entry.released_risk != self.released_risk:
            raise ValueError("released_risk mismatch")
        object.__setattr__(
            self,
            "warnings",
            _messages(self.warnings, "warnings"),
        )
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only finalization")
