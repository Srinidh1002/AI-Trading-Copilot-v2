"""Immutable PAPER order, quote evidence, and fill result contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import ClassVar

_MARKETS = {("NIFTY", "NSE"), ("SENSEX", "BSE")}
_RIGHTS = {"CALL", "PUT"}
_ORDER_TYPES = {"LIMIT", "MARKET"}
_FILL_STATUSES = {"FILLED", "REJECTED", "NOT_FILLED"}

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
    number = float(value)
    if (positive and number <= 0.0) or (not positive and number < 0.0):
        raise ValueError(name)
    return number

def _messages(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(name)
    return tuple(dict.fromkeys(_text(item, name) for item in value))

@dataclass(frozen=True, slots=True)
class PaperEntryOrderV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_entry_order.v1"
    order_id: str
    recommendation_id: str
    parent_cycle_id: str
    submitted_at: datetime
    underlying_symbol: str
    exchange: str
    option_right: str
    contract: str
    expiry: str
    strike: float
    order_type: str
    limit_price: float | None
    lots: int
    lot_size: int
    quantity: int
    maximum_capital: float
    maximum_loss: float
    maximum_slippage_fraction: float
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("order_id", "recommendation_id", "parent_cycle_id", "contract", "expiry"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "submitted_at", _aware(self.submitted_at, "submitted_at"))
        market = (_text(self.underlying_symbol, "underlying_symbol").upper(), _text(self.exchange, "exchange").upper())
        if market not in _MARKETS:
            raise ValueError("market")
        object.__setattr__(self, "underlying_symbol", market[0])
        object.__setattr__(self, "exchange", market[1])
        right = _text(self.option_right, "option_right").upper()
        if right not in _RIGHTS:
            raise ValueError("option_right")
        object.__setattr__(self, "option_right", right)
        order_type = _text(self.order_type, "order_type").upper()
        if order_type not in _ORDER_TYPES:
            raise ValueError("order_type")
        object.__setattr__(self, "order_type", order_type)
        object.__setattr__(self, "strike", _number(self.strike, "strike", positive=True))
        for name in ("maximum_capital", "maximum_loss"):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=True))
        slippage = _number(self.maximum_slippage_fraction, "maximum_slippage_fraction")
        if slippage > 1.0:
            raise ValueError("maximum_slippage_fraction")
        object.__setattr__(self, "maximum_slippage_fraction", slippage)
        if self.limit_price is not None:
            object.__setattr__(self, "limit_price", _number(self.limit_price, "limit_price", positive=True))
        if order_type == "LIMIT" and self.limit_price is None:
            raise ValueError("LIMIT requires limit_price")
        if order_type == "MARKET" and self.limit_price is not None:
            raise ValueError("MARKET cannot use limit_price")
        for name in ("lots", "lot_size", "quantity"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(name)
        if self.quantity != self.lots * self.lot_size:
            raise ValueError("quantity must equal lots * lot_size")
        if self.maximum_loss > self.maximum_capital:
            raise ValueError("maximum_loss exceeds maximum_capital")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.broker_order_submission is not False:
            raise ValueError("PAPER-only order")

@dataclass(frozen=True, slots=True)
class PaperFillQuoteEvidenceV1:
    quote_id: str
    contract: str
    observed_at: datetime
    bid_price: float
    ask_price: float
    last_price: float
    available_ask_quantity: int
    source: str
    is_stale: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("quote_id", "contract", "source"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "observed_at"))
        for name in ("bid_price", "ask_price", "last_price"):
            object.__setattr__(self, name, _number(getattr(self, name), name, positive=True))
        if self.bid_price > self.ask_price:
            raise ValueError("bid_price exceeds ask_price")
        if type(self.available_ask_quantity) is not int:
            raise TypeError("available_ask_quantity")
        if self.available_ask_quantity < 0:
            raise ValueError("available_ask_quantity")
        if type(self.is_stale) is not bool:
            raise TypeError("is_stale")
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))

@dataclass(frozen=True, slots=True)
class PaperFillResultV1:
    SCHEMA_VERSION: ClassVar[str] = "paper_fill_result.v1"
    fill_result_id: str
    order_id: str
    quote_id: str
    evaluated_at: datetime
    status: str
    filled_quantity: int
    filled_lots: int
    fill_price: float | None
    gross_premium_outlay: float
    slippage_amount_per_unit: float
    slippage_fraction: float
    remaining_quantity: int
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        for name in ("fill_result_id", "order_id", "quote_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at"))
        status = _text(self.status, "status").upper()
        if status not in _FILL_STATUSES:
            raise ValueError("status")
        object.__setattr__(self, "status", status)
        for name in ("filled_quantity", "filled_lots", "remaining_quantity"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(name)
        if self.fill_price is not None:
            object.__setattr__(self, "fill_price", _number(self.fill_price, "fill_price", positive=True))
        for name in ("gross_premium_outlay", "slippage_amount_per_unit", "slippage_fraction"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        object.__setattr__(self, "blockers", _messages(self.blockers, "blockers"))
        object.__setattr__(self, "warnings", _messages(self.warnings, "warnings"))
        if status == "FILLED":
            if self.fill_price is None or self.filled_quantity <= 0 or self.filled_lots <= 0 or self.remaining_quantity != 0 or self.blockers:
                raise ValueError("FILLED coherence")
        else:
            if self.fill_price is not None or self.filled_quantity != 0 or self.filled_lots != 0 or self.gross_premium_outlay != 0.0 or self.slippage_amount_per_unit != 0.0 or self.slippage_fraction != 0.0 or not self.blockers:
                raise ValueError("non-filled coherence")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False or self.broker_order_submission is not False:
            raise ValueError("PAPER-only fill result")
