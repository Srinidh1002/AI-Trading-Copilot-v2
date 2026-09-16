"""Static provider-neutral five-market PAPER universe.

This module contains no provider authentication, market-data calls,
contract-token lookup, lot sizes, tick sizes, or trading decisions.
"""

from __future__ import annotations

from services.contracts.trading_market_v2 import (
    TradingMarketV2,
)
from services.contracts.trading_universe_v2 import (
    TradingUniverseV2,
)


TARGET_FIVE_MARKETS = (
    TradingMarketV2(
        symbol="NIFTY",
        display_name="NIFTY 50",
        market_type="INDEX",
        underlying_exchange="NSE",
        derivative_exchange="NFO",
        aliases=(
            "NIFTY50",
            "NIFTY 50",
        ),
    ),
    TradingMarketV2(
        symbol="SENSEX",
        display_name="BSE SENSEX",
        market_type="INDEX",
        underlying_exchange="BSE",
        derivative_exchange="BFO",
        aliases=(
            "BSE SENSEX",
        ),
    ),
    TradingMarketV2(
        symbol="CRUDEOILM",
        display_name="Crude Oil Mini",
        market_type="COMMODITY",
        underlying_exchange="MCX",
        derivative_exchange="MCX",
        aliases=(
            "CRUDE OIL MINI",
        ),
    ),
    TradingMarketV2(
        symbol="GOLDM",
        display_name="Gold Mini",
        market_type="COMMODITY",
        underlying_exchange="MCX",
        derivative_exchange="MCX",
        aliases=(
            "GOLD MINI",
        ),
    ),
    TradingMarketV2(
        symbol="NATGASMINI",
        display_name="Natural Gas Mini",
        market_type="COMMODITY",
        underlying_exchange="MCX",
        derivative_exchange="MCX",
        aliases=(
            "NATURAL GAS MINI",
            "NAT GAS MINI",
        ),
    ),
)


TARGET_FIVE_MARKET_UNIVERSE = TradingUniverseV2(
    universe_name="FIVE_MARKET_PAPER_V2",
    markets=TARGET_FIVE_MARKETS,
)


TARGET_FIVE_MARKET_IDENTITIES = tuple(
    market.identity
    for market in TARGET_FIVE_MARKETS
)


TARGET_FIVE_MARKET_SYMBOLS = tuple(
    market.symbol
    for market in TARGET_FIVE_MARKETS
)


_BY_SYMBOL = {
    market.symbol: market
    for market in TARGET_FIVE_MARKETS
}


_ALIAS_TO_SYMBOL = {
    alias: market.symbol
    for market in TARGET_FIVE_MARKETS
    for alias in (
        market.symbol,
        *market.aliases,
    )
}


def _normalise(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = " ".join(value.upper().split())
    return value or None


def normalize_target_market_symbol(
    value: object,
) -> str | None:
    """Return one of the five canonical symbols, or None."""

    normalized = _normalise(value)

    if normalized is None:
        return None

    return _ALIAS_TO_SYMBOL.get(
        normalized
    )


def get_target_market(
    value: object,
    exchange: object = None,
) -> TradingMarketV2:
    """Resolve a canonical target market without provider I/O."""

    symbol = normalize_target_market_symbol(
        value
    )

    if symbol is None:
        raise ValueError(
            "Unsupported five-market symbol."
        )

    market = _BY_SYMBOL[symbol]

    if exchange is not None:
        actual_exchange = _normalise(
            exchange
        )

        if (
            actual_exchange
            != market.underlying_exchange
        ):
            raise ValueError(
                "Target-market exchange mismatch."
            )

    return market


def is_target_market(
    value: object,
    exchange: object = None,
) -> bool:
    try:
        get_target_market(
            value,
            exchange,
        )
    except ValueError:
        return False

    return True


def list_target_markets() -> tuple[
    TradingMarketV2,
    ...,
]:
    return TARGET_FIVE_MARKETS
