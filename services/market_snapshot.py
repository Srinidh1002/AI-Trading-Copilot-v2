from services.live_multi_timeframe_data import LiveMultiTimeframeData

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

    latest = df.iloc[-1]

    return {
        "ltp": latest["Close"],
        "open": latest["Open"],
        "high": latest["High"],
        "low": latest["Low"],
        "close": latest["Close"],
    }