import pandas as pd


def calculate_indicators(df: pd.DataFrame):

    data = df.copy()

    # ============================
    # Exponential Moving Averages
    # ============================

    data["EMA20"] = (
        data["Close"]
        .ewm(span=20, adjust=False)
        .mean()
    )

    data["EMA50"] = (
        data["Close"]
        .ewm(span=50, adjust=False)
        .mean()
    )

    data["EMA200"] = (
        data["Close"]
        .ewm(span=200, adjust=False)
        .mean()
    )

    latest = data.iloc[-1]

    return {
        "EMA20": float(latest["EMA20"]),
        "EMA50": float(latest["EMA50"]),
        "EMA200": float(latest["EMA200"]),
    }