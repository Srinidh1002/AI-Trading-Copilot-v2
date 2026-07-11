"""Cached resolution of application symbols to Dhan security metadata."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DhanInstrument:
    symbol: str
    security_id: str
    exchange_segment: str
    instrument_type: str
    expiry: str | None = None
    strike: float | None = None
    option_type: str | None = None


class InstrumentRegistry:
    """Resolve built-in indices and locally cached option-contract metadata."""

    def __init__(self, loader: Callable[[], Iterable[Mapping[str, Any]]] | None = None) -> None:
        self._loader = loader
        self._instruments = [
            DhanInstrument("NIFTY", "13", "IDX_I", "INDEX"),
            DhanInstrument("BANKNIFTY", "25", "IDX_I", "INDEX"),
        ]

    def refresh(self) -> int:
        """Explicitly load metadata; ordinary resolution never calls a network."""

        if self._loader is None:
            raise RuntimeError("No instrument loader is configured.")
        return self.register_many(self._loader())

    def register_many(self, records: Iterable[Mapping[str, Any]]) -> int:
        """Normalise and cache compact or detailed Dhan security-list records."""

        added = 0
        for record in records:
            item = self._from_record(record)
            if item and item not in self._instruments:
                self._instruments.append(item)
                added += 1
        return added

    def resolve(self, symbol: str, *, expiry: str | None = None, strike: float | None = None, option_type: str | None = None) -> DhanInstrument:
        """Resolve an index or a cached option contract to Dhan metadata."""

        symbol = self._normalise(symbol, "symbol")
        expiry = self._normalise(expiry, "expiry") if expiry else None
        option_type = self._normalise(option_type, "option_type") if option_type else None
        for item in self._instruments:
            if item.symbol == symbol and (expiry is None or item.expiry == expiry) and (strike is None or item.strike == float(strike)) and (option_type is None or item.option_type == option_type):
                return item
        raise KeyError(f"No cached Dhan instrument matches {symbol}.")

    def resolve_option(self, underlying_symbol: str, expiry: str, strike: float, option_type: str) -> DhanInstrument:
        return self.resolve(underlying_symbol, expiry=expiry, strike=strike, option_type=option_type)

    @property
    def cached_instruments(self) -> tuple[DhanInstrument, ...]:
        return tuple(self._instruments)

    @classmethod
    def _from_record(cls, record: Mapping[str, Any]) -> DhanInstrument | None:
        def value(*names: str) -> str:
            for name in names:
                raw = record.get(name)
                if raw is not None and str(raw).strip():
                    return str(raw).strip()
            return ""

        symbol = value("symbol", "underlying_symbol", "SM_SYMBOL_NAME", "SYMBOL_NAME")
        security_id = value("security_id", "SECURITY_ID", "SEM_SM_SECURITY_ID")
        segment = value("exchange_segment", "EXCHANGE_SEGMENT", "SEM_EXM_EXCH_ID")
        kind = value("instrument_type", "INSTRUMENT_TYPE", "SEM_EXCH_INSTRUMENT_TYPE")
        if not all((symbol, security_id, segment, kind)):
            return None
        strike_text = value("strike", "strike_price", "STRIKE_PRICE", "SEM_STRIKE_PRICE")
        try:
            strike = float(strike_text) if strike_text else None
        except ValueError:
            strike = None
        expiry = value("expiry", "EXPIRY_DATE", "SEM_EXPIRY_DATE")
        option_type = value("option_type", "OPTION_TYPE", "SEM_OPTION_TYPE")
        return DhanInstrument(cls._normalise(symbol, "symbol"), security_id, cls._normalise(segment, "exchange_segment"), cls._normalise(kind, "instrument_type"), cls._normalise(expiry, "expiry") if expiry else None, strike, cls._normalise(option_type, "option_type") if option_type else None)

    @staticmethod
    def _normalise(value: str | None, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value.strip().upper()
