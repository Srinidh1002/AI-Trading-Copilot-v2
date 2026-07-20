"""
Decision Logger V1
"""

from datetime import datetime

from services.database import log_decision


def log_ai_decision(

    snapshot,

    trend,

    candle,

    support,

    decision,

    confidence,

    risk,

):

    indicators = snapshot["indicators"]

    log_decision({

        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        "symbol": snapshot.get(
            "symbol",
            "NIFTY"
        ),

        "price": snapshot["ltp"],

        "signal": decision["signal"],

        "confidence": confidence["confidence"],

        "bull_score": confidence["bull_score"],

        "bear_score": confidence["bear_score"],

        "neutral_score": confidence["neutral_score"],

        "entry": risk["ENTRY"],

        "stop_loss": risk["STOP_LOSS"],

        "target1": risk["TARGET1"],

        "target2": risk["TARGET2"],

        "support": support.get("support", support.get("Support")),

        "resistance": support.get("resistance", support.get("Resistance")),

        "trend": trend["trend"],

        "pattern": candle["pattern"],

        "reason": decision["reason"],

        "rsi": indicators["RSI"],

        "adx": indicators["ADX"],

        "atr": indicators["ATR"],

        "ema20": indicators["EMA20"],

        "ema50": indicators["EMA50"],

        "ema200": indicators["EMA200"],

        "macd": indicators["MACD"],

        "macd_signal": indicators["MACD_SIGNAL"],

        "vwap": indicators["VWAP"],

    })