"""Deterministic P5-8 replay builders using fixed aware timestamps."""

from datetime import datetime, timedelta, timezone

from services.contracts.market_breadth_snapshot_v1 import (
    MarketBreadthSnapshotV1,
)
from services.contracts.market_candle_series_v1 import (
    MarketCandleSeriesV1,
)
from services.contracts.market_candle_v1 import (
    MarketCandleV1,
)
from services.contracts.market_data_provenance_v1 import (
    MarketDataProvenanceV1,
)
from services.contracts.volatility_snapshot_v1 import (
    VolatilitySnapshotV1,
)


NOW = datetime(
    2026,
    1,
    1,
    12,
    tzinfo=timezone.utc,
)

PAIRS = (
    ("NIFTY", "NSE", "SENSEX", "BSE"),
    ("SENSEX", "BSE", "NIFTY", "NSE"),
    ("BANKNIFTY", "NSE", "FINNIFTY", "NSE"),
    ("FINNIFTY", "NSE", "BANKNIFTY", "NSE"),
)

DEFAULT_RETURNS = tuple(
    0.002 + (index * 0.0001)
    for index in range(30)
)


def series(
    symbol,
    exchange,
    returns=None,
):
    returns = (
        DEFAULT_RETURNS
        if returns is None
        else tuple(returns)
    )

    price = 100.0
    values = [price]

    for return_value in returns:
        price *= 1.0 + return_value
        values.append(price)

    candles = []

    for index, value in enumerate(values):
        start = (
            NOW
            - timedelta(
                minutes=(len(values) - index) * 5
            )
        )

        provenance = MarketDataProvenanceV1(
            "TEST",
            symbol,
            exchange,
            "TEST",
            start,
            start,
            False,
            None,
            None,
        )

        candles.append(
            MarketCandleV1(
                f"{symbol}-{index}",
                symbol,
                exchange,
                "5m",
                start,
                start + timedelta(minutes=5),
                value,
                value,
                value,
                value,
                1,
                True,
                provenance,
            )
        )

    return MarketCandleSeriesV1(
        f"{symbol}-series",
        symbol,
        exchange,
        "5m",
        tuple(candles),
        None,
        None,
        NOW,
    )


def breadth(
    symbol,
    exchange,
    advance=60,
    decline=30,
    unchanged=10,
):
    total = (
        advance
        + decline
        + unchanged
    )

    return MarketBreadthSnapshotV1(
        "breadth",
        NOW,
        symbol,
        exchange,
        "breadth-source",
        NOW,
        advance,
        decline,
        unchanged,
        total,
        total,
        "CONFIRMS",
    )


def volatility(
    symbol,
    exchange,
    regime="NORMAL",
    change=0.0,
):
    return VolatilitySnapshotV1(
        "vix",
        NOW,
        symbol,
        exchange,
        "INDIA_VIX",
        "NSE",
        "vix-source",
        NOW,
        15,
        None,
        change,
        regime,
    )