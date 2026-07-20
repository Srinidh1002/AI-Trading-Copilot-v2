"""
Master Indicator Engine

Calculates all technical indicators once and returns
the latest values along with the enriched dataframe.
"""

import pandas as pd
import ta


def calculate_indicators(df: pd.DataFrame):

    data = df.copy()

    # -------------------------------------------------
    # Standardize Column Names
    # -------------------------------------------------

    data.columns = [c.lower() for c in data.columns]

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for col in required:
        if col not in data.columns:
            raise ValueError(f"Missing column: {col}")

    # -------------------------------------------------
    # EMA
    # -------------------------------------------------

    data["EMA20"] = ta.trend.EMAIndicator(
        close=data["close"],
        window=20,
    ).ema_indicator()

    data["EMA50"] = ta.trend.EMAIndicator(
        close=data["close"],
        window=50,
    ).ema_indicator()

    data["EMA200"] = ta.trend.EMAIndicator(
        close=data["close"],
        window=200,
    ).ema_indicator()

    # -------------------------------------------------
    # RSI
    # -------------------------------------------------

    data["RSI"] = ta.momentum.RSIIndicator(
        close=data["close"],
        window=14,
    ).rsi()

    # -------------------------------------------------
    # MACD
    # -------------------------------------------------

    macd = ta.trend.MACD(
        close=data["close"]
    )

    data["MACD"] = macd.macd()

    data["MACD_SIGNAL"] = macd.macd_signal()

    data["MACD_HIST"] = macd.macd_diff()

    # -------------------------------------------------
    # ADX
    # -------------------------------------------------

    adx = ta.trend.ADXIndicator(

        high=data["high"],

        low=data["low"],

        close=data["close"],

        window=14,

    )

    data["ADX"] = adx.adx()

    data["+DI"] = adx.adx_pos()

    data["-DI"] = adx.adx_neg()

    # -------------------------------------------------
    # ATR
    # -------------------------------------------------

    atr = ta.volatility.AverageTrueRange(

        high=data["high"],

        low=data["low"],

        close=data["close"],

        window=14,

    )

    data["ATR"] = atr.average_true_range()

    # -------------------------------------------------
    # VWAP
    # -------------------------------------------------

    vwap = ta.volume.VolumeWeightedAveragePrice(

        high=data["high"],

        low=data["low"],

        close=data["close"],

        volume=data["volume"],

    )

    data["VWAP"] = vwap.volume_weighted_average_price()

    # -------------------------------------------------
    # Bollinger Bands
    # -------------------------------------------------

    bb = ta.volatility.BollingerBands(

        close=data["close"],

        window=20,

        window_dev=2,

    )

    data["BB_UPPER"] = bb.bollinger_hband()

    data["BB_MIDDLE"] = bb.bollinger_mavg()

    data["BB_LOWER"] = bb.bollinger_lband()

    # -------------------------------------------------
    # Volume Average
    # -------------------------------------------------

    data["VOL_MA20"] = (

        data["volume"]

        .rolling(20)

        .mean()

    )

    # -------------------------------------------------
    # Latest Row
    # -------------------------------------------------

    latest = data.iloc[-1]

    indicators = {

        "EMA20": float(latest["EMA20"]),

        "EMA50": float(latest["EMA50"]),

        "EMA200": float(latest["EMA200"]),

        "RSI": float(latest["RSI"]),

        "MACD": float(latest["MACD"]),

        "MACD_SIGNAL": float(latest["MACD_SIGNAL"]),

        "MACD_HIST": float(latest["MACD_HIST"]),

        "ADX": float(latest["ADX"]),

        "DI_PLUS": float(latest["+DI"]),

        "DI_MINUS": float(latest["-DI"]),

        "ATR": float(latest["ATR"]),

        "VWAP": float(latest["VWAP"]),

        "BB_UPPER": float(latest["BB_UPPER"]),

        "BB_MIDDLE": float(latest["BB_MIDDLE"]),

        "BB_LOWER": float(latest["BB_LOWER"]),

        "VOLUME": float(latest["volume"]),

        "VOL_MA20": float(latest["VOL_MA20"]),

        "OPEN": float(latest["open"]),

        "HIGH": float(latest["high"]),

        "LOW": float(latest["low"]),

        "CLOSE": float(latest["close"]),

    }

    return data, indicators