"""Per-market trading parameter registry for the canonical PAPER bot.

Carries exactly the parameters that vary across markets and affect trading
behavior: spot identity (as consumed by the legacy Angel-shaped data API),
contract specs, target/SL policy, session hours, instrument symbol filters,
WebSocket subscription hints, and expiry-selection policy.

This module does NOT carry:
  * provider routing         -> services/core/provider_routing_policy_v2.py
  * identity aliases         -> services/core/market_identity.py
  * the market list          -> services/core/five_market_universe_v2.py
  * strategy version/epoch   -> per-engine, not per-market

Adding a new market means adding one entry to MARKET_TRADING_CONFIGS. No
engine code changes are required for the fields carried here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketTradingConfigV2:
    symbol: str
    market_type: str                 # "INDEX" | "COMMODITY"
    underlying_exchange: str         # NSE / BSE / MCX
    derivative_exchange: str         # NFO / BFO / MCX

    # Spot identity as consumed by the legacy Angel-shaped data API.
    # FYERS conversion happens in the identity resolver, not here.
    index_token: str
    index_symbol: str

    # Contract specs.
    lot_size: int
    strike_interval: float
    strike_divisor: float

    # Weighted-constituent universe for breadth / top-weight analysis.
    top_stocks: tuple[str, ...]

    # Exit policy.
    t1_pct: float
    t2_pct: float
    t3_pct: float
    stop_loss_pct: float

    # Session hours in IST as (hour, minute).
    market_open_hhmm: tuple[int, int]
    market_close_hhmm: tuple[int, int]
    final_exit_hhmm: tuple[int, int]

    # Instrument-master filter: symbol must contain the substring, and
    # must NOT contain any of the excluded substrings. Applied verbatim
    # by load_instruments().
    symbol_must_contain: str
    symbol_must_not_contain: tuple[str, ...]

    # WebSocket subscription hints.
    ws_exchange_segment: str         # e.g. "NSE_CM" / "BSE_CM"
    ws_spot_token: str               # provider spot token for the underlying

    # Expiry policy: when True, a same-day (0 DTE) nearest expiry is
    # skipped in favour of the next valid expiry. Used by get_expiry().
    exclude_same_day_expiry: bool


_TOP_STOCKS_INDIA_INDEX = (
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
    "ITC", "KOTAKBANK", "LT", "SBIN", "BHARTIARTL",
)


MARKET_TRADING_CONFIGS: dict[str, MarketTradingConfigV2] = {
    "NIFTY": MarketTradingConfigV2(
        symbol="NIFTY",
        market_type="INDEX",
        underlying_exchange="NSE",
        derivative_exchange="NFO",
        index_token="99926000",
        index_symbol="NIFTY",
        lot_size=75,
        strike_interval=50,
        strike_divisor=100,
        top_stocks=_TOP_STOCKS_INDIA_INDEX,
        t1_pct=15,
        t2_pct=30,
        t3_pct=50,
        stop_loss_pct=5,
        market_open_hhmm=(9, 15),
        market_close_hhmm=(15, 30),
        final_exit_hhmm=(15, 28),
        symbol_must_contain="NIFTY",
        symbol_must_not_contain=("BANKNIFTY", "FINNIFTY"),
        ws_exchange_segment="NSE_CM",
        ws_spot_token="99926000",
        exclude_same_day_expiry=False,
    ),
    "SENSEX": MarketTradingConfigV2(
        symbol="SENSEX",
        market_type="INDEX",
        underlying_exchange="BSE",
        derivative_exchange="BFO",
        index_token="1",
        index_symbol="SENSEX",
        lot_size=20,
        strike_interval=100,
        strike_divisor=100,
        top_stocks=_TOP_STOCKS_INDIA_INDEX,
        t1_pct=15,
        t2_pct=30,
        t3_pct=50,
        stop_loss_pct=5,
        market_open_hhmm=(9, 15),
        market_close_hhmm=(15, 30),
        final_exit_hhmm=(15, 28),
        symbol_must_contain="SENSEX",
        symbol_must_not_contain=("SENSEX50",),
        ws_exchange_segment="BSE_CM",
        ws_spot_token="1",
        exclude_same_day_expiry=True,
    ),
}


def get_market_trading_config(symbol: object) -> MarketTradingConfigV2:
    """Return the trading config for a canonical market symbol.

    Raises ValueError for unknown/empty/non-string input. Case-insensitive,
    whitespace-normalising.
    """
    if not isinstance(symbol, str):
        raise ValueError("Market symbol must be a string.")
    key = " ".join(symbol.upper().split())
    if not key:
        raise ValueError("Market symbol is empty.")
    config = MARKET_TRADING_CONFIGS.get(key)
    if config is None:
        raise ValueError(f"Unsupported market: {symbol!r}")
    return config


def is_supported_trading_market(symbol: object) -> bool:
    try:
        get_market_trading_config(symbol)
    except ValueError:
        return False
    return True
