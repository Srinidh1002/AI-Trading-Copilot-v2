"""PAPER-only five-market trading-universe contract."""

from __future__ import annotations

from dataclasses import dataclass
import json

from services.contracts.trading_market_v2 import (
    TradingMarketV2,
)


@dataclass(frozen=True, slots=True)
class TradingUniverseV2:
    """Immutable target universe for provider-neutral PAPER work."""

    universe_name: str
    markets: tuple[TradingMarketV2, ...]
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "trading_universe.v2"

    def __post_init__(self) -> None:
        if (
            self.universe_name
            != "FIVE_MARKET_PAPER_V2"
        ):
            raise ValueError(
                "Invalid five-market universe name."
            )

        if not isinstance(self.markets, tuple):
            raise ValueError(
                "Trading markets must be a tuple."
            )

        if len(self.markets) != 5:
            raise ValueError(
                "Five-market universe requires exactly five markets."
            )

        if not all(
            isinstance(market, TradingMarketV2)
            for market in self.markets
        ):
            raise ValueError(
                "Invalid trading-market member."
            )

        identities = tuple(
            market.identity
            for market in self.markets
        )

        symbols = tuple(
            market.symbol
            for market in self.markets
        )

        if len(set(identities)) != len(identities):
            raise ValueError(
                "Duplicate trading-market identity."
            )

        if len(set(symbols)) != len(symbols):
            raise ValueError(
                "Duplicate trading-market symbol."
            )

        aliases = tuple(
            alias
            for market in self.markets
            for alias in market.aliases
        )

        if len(set(aliases)) != len(aliases):
            raise ValueError(
                "Duplicate alias across trading universe."
            )

        if self.execution_mode != "PAPER":
            raise ValueError(
                "Five-market foundation is PAPER only."
            )

        if self.live_execution_eligible is not False:
            raise ValueError(
                "Live execution is not eligible."
            )

        if (
            self.schema_version
            != "trading_universe.v2"
        ):
            raise ValueError(
                "Invalid trading-universe schema."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "universe_name": self.universe_name,
            "markets": [
                market.to_dict()
                for market in self.markets
            ],
            "execution_mode": self.execution_mode,
            "live_execution_eligible": False,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )
