"""Provider-neutral canonical target-market identity contract."""

from __future__ import annotations

from dataclasses import dataclass
import json


_INDEX_DERIVATIVE_EXCHANGE = {
    "NSE": "NFO",
    "BSE": "BFO",
}


def _normalise(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = " ".join(value.upper().split())
    return value or None


@dataclass(frozen=True, slots=True)
class TradingMarketV2:
    """Stable market-root identity, independent of a data provider."""

    symbol: str
    display_name: str
    market_type: str
    underlying_exchange: str
    derivative_exchange: str
    aliases: tuple[str, ...]
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    enabled: bool = True
    schema_version: str = "trading_market.v2"

    def __post_init__(self) -> None:
        symbol = _normalise(self.symbol)
        display_name = (
            " ".join(self.display_name.split())
            if isinstance(self.display_name, str)
            else ""
        )
        market_type = _normalise(self.market_type)
        underlying_exchange = _normalise(
            self.underlying_exchange
        )
        derivative_exchange = _normalise(
            self.derivative_exchange
        )

        if not symbol or " " in symbol:
            raise ValueError(
                "Invalid canonical trading-market symbol."
            )

        if not display_name:
            raise ValueError(
                "Trading-market display name is required."
            )

        if market_type not in {
            "INDEX",
            "COMMODITY",
        }:
            raise ValueError(
                "Unsupported trading-market type."
            )

        if market_type == "INDEX":
            expected_derivative = (
                _INDEX_DERIVATIVE_EXCHANGE.get(
                    underlying_exchange
                )
            )

            if (
                expected_derivative is None
                or derivative_exchange
                != expected_derivative
            ):
                raise ValueError(
                    "Invalid index exchange topology."
                )

        if market_type == "COMMODITY":
            if (
                underlying_exchange != "MCX"
                or derivative_exchange != "MCX"
            ):
                raise ValueError(
                    "Invalid commodity exchange topology."
                )

        if self.currency != "INR":
            raise ValueError(
                "Only INR target markets are supported."
            )

        if self.timezone != "Asia/Kolkata":
            raise ValueError(
                "Invalid target-market timezone."
            )

        if self.enabled is not True:
            raise ValueError(
                "Target market must be enabled."
            )

        if (
            self.schema_version
            != "trading_market.v2"
        ):
            raise ValueError(
                "Invalid trading-market schema."
            )

        if not isinstance(self.aliases, tuple):
            raise ValueError(
                "Aliases must be a tuple."
            )

        aliases = tuple(
            _normalise(alias) or ""
            for alias in self.aliases
        )

        if any(not alias for alias in aliases):
            raise ValueError(
                "Invalid trading-market alias."
            )

        if len(set(aliases)) != len(aliases):
            raise ValueError(
                "Duplicate trading-market alias."
            )

        if symbol in aliases:
            raise ValueError(
                "Canonical symbol cannot repeat as alias."
            )

        object.__setattr__(
            self,
            "symbol",
            symbol,
        )
        object.__setattr__(
            self,
            "display_name",
            display_name,
        )
        object.__setattr__(
            self,
            "market_type",
            market_type,
        )
        object.__setattr__(
            self,
            "underlying_exchange",
            underlying_exchange,
        )
        object.__setattr__(
            self,
            "derivative_exchange",
            derivative_exchange,
        )
        object.__setattr__(
            self,
            "aliases",
            aliases,
        )

    @property
    def identity(self) -> tuple[str, str]:
        return (
            self.symbol,
            self.underlying_exchange,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "display_name": self.display_name,
            "market_type": self.market_type,
            "underlying_exchange": (
                self.underlying_exchange
            ),
            "derivative_exchange": (
                self.derivative_exchange
            ),
            "aliases": list(self.aliases),
            "currency": self.currency,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
