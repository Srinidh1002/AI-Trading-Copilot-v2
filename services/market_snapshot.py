"""
Market Snapshot Service V2
"""

from datetime import datetime

from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.indicator_engine import calculate_indicators


EXCHANGE = "NSE"
SYMBOL_TOKEN = "99926000"


def get_market_snapshot():

    service = LiveMultiTimeframeData()

    df = service.fetch_timeframe(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        timeframe="5m",
    )

    if df.empty:
        raise ValueError("No market data received.")

    df.columns = [c.lower() for c in df.columns]

    data, indicators = calculate_indicators(df)

    latest = data.iloc[-1]

    now = datetime.now()

    market_open = (
        now.weekday() < 5
        and (
            now.hour > 9
            or (now.hour == 9 and now.minute >= 15)
        )
        and (
            now.hour < 15
            or (now.hour == 15 and now.minute <= 30)
        )
    )

    return {

        "symbol": "NIFTY",

        "history": data,

        "ltp": float(latest["close"]),

        "open": float(latest["open"]),

        "high": float(latest["high"]),

        "low": float(latest["low"]),

        "close": float(latest["close"]),

        "volume": float(latest["volume"]),

        "timestamp": str(
            latest.name
        ),

        "refresh_time": now.strftime("%H:%M:%S"),

        "market_status":
            "OPEN"
            if market_open
            else "CLOSED",

        "indicators": indicators,

    }