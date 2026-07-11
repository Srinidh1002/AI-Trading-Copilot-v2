"""Broker-neutral, read-only market-data interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class BrokerError(RuntimeError):
    """Raised when a broker data provider cannot fulfil a request."""


class BaseBroker(ABC):
    """Data contract that keeps intelligence services broker independent."""

    @abstractmethod
    def get_quote(self, security_id: str, exchange_segment: str) -> Mapping[str, Any]: ...

    @abstractmethod
    def get_historical_data(self, security_id: str, exchange_segment: str, instrument_type: str, from_date: str, to_date: str, *, expiry_code: int = 0, include_oi: bool = False) -> Mapping[str, Any]: ...

    @abstractmethod
    def get_intraday_data(self, security_id: str, exchange_segment: str, instrument_type: str, from_date: str, to_date: str, *, interval: int = 1, include_oi: bool = False) -> Mapping[str, Any]: ...

    @abstractmethod
    def get_option_chain(self, underlying_security_id: str, underlying_exchange_segment: str, expiry: str) -> Mapping[str, Any]: ...

    @abstractmethod
    def get_expiry_list(self, underlying_security_id: str, underlying_exchange_segment: str) -> Mapping[str, Any]: ...
