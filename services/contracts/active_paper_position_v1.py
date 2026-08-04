"""Immutable active PAPER position contract for Task 5 lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar


_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_RIGHTS = {"CALL", "PUT"}
_STATES = {"OPEN", "PARTIALLY_EXITED", "CLOSED"}


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
    number = float(value)
    if positive and number <= 0.0:
        raise ValueError(name)
    if not positive and not allow_negative and number < 0.0:
        raise ValueError(name)
    return number


def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))


@dataclass(frozen=True, slots=True)
class ActivePaperPositionV1:
    SCHEMA_VERSION: ClassVar[str] = "active_paper_position.v1"

    position_id: str
    recommendation_id: str
    reservation_result_id: str
    fill_result_id: str
    opened_at: datetime
    updated_at: datetime
    underlying_symbol: str
    exchange: str
    option_right: str
    contract: str
    expiry: str
    strike: float
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    target_3: float
    initial_lots: int
    remaining_lots: int
    lot_size: int
    initial_quantity: int
    remaining_quantity: int
    reserved_capital: float
    maximum_loss: float
    lifecycle_state: str = "OPEN"
    target_1_hit: bool = False
    target_2_hit: bool = False
    target_3_hit: bool = False
    current_stop_loss: float | None = None
    realized_pnl: float = 0.0
    processed_event_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in (
            "position_id",
            "recommendation_id",
            "reservation_result_id",
            "fill_result_id",
            "contract",
            "expiry",
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
            "updated_at",
            _aware(self.updated_at, "updated_at"),
        )
        if self.updated_at < self.opened_at:
            raise ValueError("updated_at precedes opened_at")

        market = (
            _text(
                self.underlying_symbol,
                "underlying_symbol",
            ).upper(),
            _text(self.exchange, "exchange").upper(),
        )
        if market not in _MARKETS:
            raise ValueError("market")
        object.__setattr__(
            self,
            "underlying_symbol",
            market[0],
        )
        object.__setattr__(self, "exchange", market[1])

        right = _text(self.option_right, "option_right").upper()
        if right not in _RIGHTS:
            raise ValueError("option_right")
        object.__setattr__(self, "option_right", right)

        state = _text(
            self.lifecycle_state,
            "lifecycle_state",
        ).upper()
        if state not in _STATES:
            raise ValueError("lifecycle_state")
        object.__setattr__(self, "lifecycle_state", state)

        for name in (
            "strike",
            "entry_price",
            "stop_loss",
            "target_1",
            "target_2",
            "target_3",
            "reserved_capital",
            "maximum_loss",
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
        if self.current_stop_loss is None:
            object.__setattr__(
                self,
                "current_stop_loss",
                self.stop_loss,
            )
        else:
            object.__setattr__(
                self,
                "current_stop_loss",
                _number(
                    self.current_stop_loss,
                    "current_stop_loss",
                    positive=True,
                ),
            )

        if not (
            self.stop_loss
            < self.entry_price
            < self.target_1
            < self.target_2
            < self.target_3
        ):
            raise ValueError("trade geometry")
        if self.current_stop_loss > self.target_3:
            raise ValueError("current_stop_loss")

        for name in (
            "initial_lots",
            "remaining_lots",
            "lot_size",
            "initial_quantity",
            "remaining_quantity",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(name)
        if self.initial_lots < 1 or self.lot_size < 1:
            raise ValueError("initial size")
        if self.initial_quantity != self.initial_lots * self.lot_size:
            raise ValueError("initial_quantity")
        if self.remaining_lots > self.initial_lots:
            raise ValueError("remaining_lots")
        if self.remaining_quantity != self.remaining_lots * self.lot_size:
            raise ValueError("remaining_quantity")

        for name in (
            "target_1_hit",
            "target_2_hit",
            "target_3_hit",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)
        if self.target_2_hit and not self.target_1_hit:
            raise ValueError("target ordering")
        if self.target_3_hit and not self.target_2_hit:
            raise ValueError("target ordering")

        if state == "OPEN":
            if self.remaining_lots != self.initial_lots:
                raise ValueError("OPEN size")
        elif state == "PARTIALLY_EXITED":
            if not 0 < self.remaining_lots < self.initial_lots:
                raise ValueError("PARTIALLY_EXITED size")
        else:
            if self.remaining_lots != 0:
                raise ValueError("CLOSED size")

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
            raise ValueError("PAPER-only position")
