"""Immutable provider-neutral quote for one option contract."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
import math

from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES


_OPTION_TYPES = ("CALL", "PUT")


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _finite_number(value: object, *, positive: bool = False) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and (value > 0 if positive else value >= 0)
    )


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _bounded_messages(value: object) -> bool:
    return isinstance(value, tuple) and all(_nonempty_text(item) for item in value)


def _primitive(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class OptionQuoteV1:
    """One supplied CALL or PUT quote, without provider payload retention."""

    option_quote_id: str
    created_at: datetime
    underlying_symbol: str
    exchange: str
    expiry: date
    strike: float
    option_type: str
    ltp: float | None
    bid_price: float | None
    ask_price: float | None
    bid_quantity: int | None
    ask_quantity: int | None
    volume: int | None
    open_interest: int | None
    change_in_open_interest: int | None
    implied_volatility: float | None
    underlying_value: float | None
    source_timestamp: datetime
    is_complete: bool
    provider_name: str
    source_record_id: str | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "option_quote.v1"

    def __post_init__(self) -> None:
        if not _nonempty_text(self.option_quote_id):
            raise ValueError("option_quote_id must be a non-empty string.")
        if (self.underlying_symbol, self.exchange) not in SUPPORTED_MARKET_IDENTITIES:
            raise ValueError("Option quote identity must be an exact supported market identity.")
        if not isinstance(self.expiry, date) or isinstance(self.expiry, datetime):
            raise ValueError("expiry must be a date.")
        if not _finite_number(self.strike, positive=True):
            raise ValueError("strike must be finite and greater than zero.")
        if self.option_type not in _OPTION_TYPES:
            raise ValueError("option_type must be CALL or PUT.")
        if not all(_aware(value) for value in (self.created_at, self.source_timestamp)):
            raise ValueError("Option quote timestamps must be timezone-aware.")
        if not isinstance(self.is_complete, bool):
            raise ValueError("is_complete must be bool.")
        if not _nonempty_text(self.provider_name):
            raise ValueError("provider_name must be a non-empty string.")
        if self.source_record_id is not None and not _nonempty_text(self.source_record_id):
            raise ValueError("source_record_id must be a non-empty string or None.")
        if not _bounded_messages(self.blockers) or not _bounded_messages(self.warnings):
            raise ValueError("blockers and warnings must be tuples of non-empty strings.")
        for name in (
            "ltp", "bid_price", "ask_price", "implied_volatility", "underlying_value",
        ):
            value = getattr(self, name)
            if value is not None and not _finite_number(value):
                raise ValueError(f"{name} must be finite and non-negative when supplied.")
        for name in (
            "bid_quantity", "ask_quantity", "volume", "open_interest",
        ):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ValueError(f"{name} must be a non-negative integer when supplied.")
        if self.change_in_open_interest is not None and (
            not isinstance(self.change_in_open_interest, int)
            or isinstance(self.change_in_open_interest, bool)
        ):
            raise ValueError("change_in_open_interest must be an integer when supplied.")
        if self.bid_price is not None and self.ask_price is not None and self.bid_price > self.ask_price:
            diagnostics = self.blockers + self.warnings
            if not any("crossed" in item.lower() or "malformed" in item.lower() for item in diagnostics):
                raise ValueError("A crossed market requires an explicit bounded diagnostic.")
        if self.execution_mode != "PAPER" or self.live_execution_eligible is not False:
            raise ValueError("Option quote is paper-only.")
        if self.schema_version != "option_quote.v1":
            raise ValueError("Invalid option quote schema version.")

    def to_dict(self) -> dict[str, object]:
        """Return an ordered, primitive-only representation."""
        return {field.name: _primitive(getattr(self, field.name)) for field in fields(self)}
