"""
MACD Engine V1
"""


def calculate_macd(df):

    data = df.copy()

    # ==============================
    # EMAs
    # ==============================

    ema12 = data["Close"].ewm(span=12, adjust=False).mean()
    ema26 = data["Close"].ewm(span=26, adjust=False).mean()

    # ==============================
    # MACD
    # ==============================

    macd = ema12 - ema26

    signal = macd.ewm(span=9, adjust=False).mean()

    histogram = macd - signal

    latest_macd = float(macd.iloc[-1])
    latest_signal = float(signal.iloc[-1])
    latest_histogram = float(histogram.iloc[-1])

    if latest_macd > latest_signal:
        trend = "Bullish"
    else:
        trend = "Bearish"

    return {
        "MACD": latest_macd,
        "Signal": latest_signal,
        "Histogram": latest_histogram,
        "Trend": trend,
    }