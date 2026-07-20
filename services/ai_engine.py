"""
Master AI Decision Engine
"""

from datetime import datetime

from services.market_engine import market_score
from services.sentiment import sentiment_score
from services.option_ai import option_score
from services.strategy_engine import strategy_engine
from services.database import log_decision, get_connection


def ai_engine(technical):

    market = market_score()

    sentiment = sentiment_score()

    option = option_score()

    decision = strategy_engine(
        technical=technical,
        market=market,
        option=option,
        sentiment=sentiment,
    )

    option_bull = option.get("bull_score", option.get("bull", 0))
    option_bear = option.get("bear_score", option.get("bear", 0))

    sentiment_bull = sentiment.get("bull_score", sentiment.get("bull", 0))
    sentiment_bear = sentiment.get("bear_score", sentiment.get("bear", 0))

    bull_score = (
        technical.get("bull_score", 0)
        + market.get("bull_score", 0)
        + option_bull
        + sentiment_bull
    )

    bear_score = (
        technical.get("bear_score", 0)
        + market.get("bear_score", 0)
        + option_bear
        + sentiment_bear
    )

    confidence = max(bull_score, bear_score)

    indicators = technical["indicators"]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_decision({

        "timestamp": timestamp,

        "symbol": "NIFTY",

        "price": indicators["CURRENT_PRICE"],

        "signal": decision["signal"],

        "confidence": confidence,

        "bull_score": bull_score,

        "bear_score": bear_score,

        "entry": indicators["ENTRY"],

        "stop_loss": indicators["STOP_LOSS"],

        "target1": indicators["TARGET1"],

        "target2": indicators["TARGET2"],

        "support": indicators["SUPPORT"],

        "resistance": indicators["RESISTANCE"],

        "rsi": indicators["RSI"],

        "adx": indicators["ADX"],

        "atr": indicators["ATR"],

        "ema20": indicators["EMA20"],

        "ema50": indicators["EMA50"],

        "ema200": indicators["EMA200"],

        "macd": indicators["MACD"],

        "macd_signal": indicators["MACD_SIGNAL"],

    })

    # ----------------------------------------------------
    # Automatically create paper trade
    # ----------------------------------------------------

    if decision["signal"] != "HOLD":

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM paper_trades
            WHERE status='OPEN'
            """
        )

        open_trade = cursor.fetchone()[0]

        if open_trade == 0:

            cursor.execute(
                """
                INSERT INTO paper_trades(

                    timestamp,
                    signal,
                    status,
                    entry,
                    stop_loss,
                    target1,
                    target2,
                    exit_price,
                    pnl,
                    confidence,
                    reason,
                    duration

                )

                VALUES(

                    ?,?,?,?,?,?,
                    ?,?,?,?,?,?

                )
                """,
                (
                    timestamp,
                    decision["signal"],
                    "OPEN",
                    indicators["ENTRY"],
                    indicators["STOP_LOSS"],
                    indicators["TARGET1"],
                    indicators["TARGET2"],
                    None,
                    None,
                    confidence,
                    "",
                    "",
                ),
            )

            conn.commit()

        conn.close()

    return {

        "technical": technical,

        "market": market,

        "sentiment": sentiment,

        "option": option,

        "bull_score": bull_score,

        "bear_score": bear_score,

        "confidence": confidence,

        "decision": decision,

    }