"""Immutable normalized CALL/PUT row for one option strike."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
import math

from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from services.contracts.option_quote_v1 import OptionQuoteV1


def _finite_positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _messages(value: object) -> bool:
    return isinstance(value, tuple) and all(_text(item) for item in value)


def _primitive(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, OptionQuoteV1):
        return value.to_dict()
    return value


@dataclass(frozen=True, slots=True)
class OptionStrikeRowV1:
    """A strike with an honestly present CALL, PUT, or both."""

    strike_row_id: str
    underlying_symbol: str
    exchange: str
    expiry: date
    strike: float
    call: OptionQuoteV1 | None
    put: OptionQuoteV1 | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "option_strike_row.v1"

    def __post_init__(self) -> None:
        if not _text(self.strike_row_id):
            raise ValueError("strike_row_id must be a non-empty string.")
        if (self.underlying_symbol, self.exchange) not in SUPPORTED_MARKET_IDENTITIES:
            raise ValueError("Strike row identity must be an exact supported market identity.")
        if not isinstance(self.expiry, date) or isinstance(self.expiry, datetime):
            raise ValueError("expiry must be a date.")
        if not _finite_positive(self.strike):
            raise ValueError("strike must be finite and greater than zero.")
        if self.call is None and self.put is None:
            raise ValueError("A strike row requires at least one option side.")
        if self.call is not None and not isinstance(self.call, OptionQuoteV1):
            raise ValueError("call must be OptionQuoteV1 or None.")
        if self.put is not None and not isinstance(self.put, OptionQuoteV1):
            raise ValueError("put must be OptionQuoteV1 or None.")
        for quote, expected_type in ((self.call, "CALL"), (self.put, "PUT")):
            if quote is None:
                continue
            if quote.option_type != expected_type:
                raise ValueError("Quote side does not match strike row side.")
            if (
                quote.underlying_symbol,
                quote.exchange,
                quote.expiry,
                quote.strike,
            ) != (self.underlying_symbol, self.exchange, self.expiry, self.strike):
                raise ValueError("Quote identity, expiry, and strike must match its row.")
        if not _messages(self.blockers) or not _messages(self.warnings):
            raise ValueError("blockers and warnings must be tuples of non-empty strings.")
        if self.schema_version != "option_strike_row.v1":
            raise ValueError("Invalid option strike row schema version.")

    def to_dict(self) -> dict[str, object]:
        return {field.name: _primitive(getattr(self, field.name)) for field in fields(self)}
