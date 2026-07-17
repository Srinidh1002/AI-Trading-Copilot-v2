from datetime import datetime

from services.live_multi_timeframe_data import LiveMultiTimeframeData
from services.indicator_engine import calculate_indicators
from services.rsi_engine import calculate_rsi
from services.macd_engine import calculate_macd
from services.adx_engine import calculate_adx
from services.atr_engine import calculate_atr


# -----------------------------------------
# CHANGE ONLY IF REQUIRED
# -----------------------------------------

EXCHANGE = "NSE"
SYMBOL_TOKEN = "99926000"   # NIFTY 50

# -----------------------------------------


def get_market_snapshot():

    service = LiveMultiTimeframeData()

    df = service.fetch_timeframe(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        timeframe="5m",
    )
    indicators = calculate_indicators(df)
    latest = df.iloc[-1]
    rsi = calculate_rsi(df)
    macd = calculate_macd(df)
    adx = calculate_adx(df)
    atr = calculate_atr(df)


    current_time = datetime.now()

    market_open = (
        current_time.weekday() < 5 and
        (
            current_time.hour > 9 or
            (current_time.hour == 9 and current_time.minute >= 15)
        ) and
        (
            current_time.hour < 15 or
            (current_time.hour == 15 and current_time.minute <= 30)
        )
    )

    return {

        "ltp": float(latest["Close"]),

        "open": float(latest["Open"]),

        "high": float(latest["High"]),

        "low": float(latest["Low"]),

        "close": float(latest["Close"]),

        "volume": int(latest["Volume"]),

        "candle_time": str(latest["timestamp"]),

        "market_status": "OPEN" if market_open else "CLOSED",

        "refresh_time": current_time.strftime("%H:%M:%S"),

        "indicators": {
            **indicators,
            "RSI": rsi,
            "MACD": macd["MACD"],
            "MACD_SIGNAL": macd["Signal"],
            "MACD_HISTOGRAM": macd["Histogram"],
            "MACD_TREND": macd["Trend"],
            "ADX": adx["ADX"],
            "ADX_STRENGTH": adx["Strength"],
            "ATR": atr["ATR"],
            "VOLATILITY": atr["Volatility"],
        }
    }