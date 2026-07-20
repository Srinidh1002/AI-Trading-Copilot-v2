"""
Market Snapshot

Creates a single market snapshot that is shared
with every analysis engine.
"""

from dataclasses import asdict
from datetime import datetime

from services.core.snapshot_schema import Snapshot
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.core.constants import (
    EXCHANGE,
    SYMBOL_TOKEN,
    DEFAULT_TIMEFRAME,
)
from services.indicators.indicator_engine import calculate_indicators


def get_market_snapshot():

    service = LiveMultiTimeframeData()

    df = service.fetch_timeframe(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        timeframe=DEFAULT_TIMEFRAME,
    )

    latest = df.iloc[-1]

    now = datetime.now()

    market_open = (
        now.weekday() < 5
        and (
            (now.hour > 9)
            or (now.hour == 9 and now.minute >= 15)
        )
        and (
            (now.hour < 15)
            or (now.hour == 15 and now.minute <= 30)
        )
    )

    snapshot = Snapshot(
        history=df,
        ltp=float(latest["close"]),
        open=float(latest["open"]),
        high=float(latest["high"]),
        low=float(latest["low"]),
        close=float(latest["close"]),
        volume=int(latest["volume"]),
        candle_time=str(latest["timestamp"]),
        market_status="OPEN" if market_open else "CLOSED",
        refresh_time=now.strftime("%H:%M:%S"),
        indicators=calculate_indicators(df),
    )

    return asdict(snapshot)