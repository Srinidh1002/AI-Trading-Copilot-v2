"""DhanHQ implementation of the broker-neutral data interface."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.broker.base_broker import BaseBroker
from services.broker.dhan_client import DhanClient


class DhanMarketData(BaseBroker):
    """Read-only adapter; this class deliberately contains no order methods."""

    def __init__(self, client: DhanClient | None = None) -> None:
        self._client = client or DhanClient()

    def get_quote(self, security_id: str, exchange_segment: str) -> Mapping[str, Any]:
        return self._client.call("quote_data", {self._segment(exchange_segment): [str(security_id)]})

    def get_historical_data(self, security_id: str, exchange_segment: str, instrument_type: str, from_date: str, to_date: str, *, expiry_code: int = 0, include_oi: bool = False) -> Mapping[str, Any]:
        return self._client.call("historical_daily_data", str(security_id), self._segment(exchange_segment), self._required(instrument_type, "instrument_type"), self._required(from_date, "from_date"), self._required(to_date, "to_date"), expiry_code=int(expiry_code), oi=bool(include_oi))

    def get_intraday_data(self, security_id: str, exchange_segment: str, instrument_type: str, from_date: str, to_date: str, *, interval: int = 1, include_oi: bool = False) -> Mapping[str, Any]:
        if interval not in {1, 5, 15, 25, 60}:
            raise ValueError("interval must be one of 1, 5, 15, 25, or 60")
        return self._client.call("intraday_minute_data", str(security_id), self._segment(exchange_segment), self._required(instrument_type, "instrument_type"), self._required(from_date, "from_date"), self._required(to_date, "to_date"), interval=interval, oi=bool(include_oi))

    def get_option_chain(self, underlying_security_id: str, underlying_exchange_segment: str, expiry: str) -> Mapping[str, Any]:
        return self._client.call("option_chain", str(underlying_security_id), self._segment(underlying_exchange_segment), self._required(expiry, "expiry"))

    def get_expiry_list(self, underlying_security_id: str, underlying_exchange_segment: str) -> Mapping[str, Any]:
        return self._client.call("expiry_list", str(underlying_security_id), self._segment(underlying_exchange_segment))

    @staticmethod
    def _required(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _segment(cls, value: str) -> str:
        return cls._required(value, "exchange_segment").upper()
