"""
Trade Engine V3
"""

from datetime import datetime
import sqlite3

from services.database import log_decision
from services.trend_engine import analyze_trend
from services.support_resistance_engine import calculate_support_resistance
from services.candlestick_engine import detect_pattern
from services.confidence_engine import calculate_confidence
from services.risk_management_engine import calculate_trade_levels

DB = "database/ai_trading.db"


# ==========================================================
# Save Trade
# ==========================================================

def save_trade(trade):

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM paper_trades
        WHERE status='OPEN'
    """)

    if cursor.fetchone()[0] > 0:
        conn.close()
        return

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

            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            trade["decision"],

            "OPEN",

            trade["entry"],

            trade["stop_loss"],

            trade["target1"],

            trade["target2"],

            None,

            None,

            trade["confidence"],

            trade["reason"],

            ""

        ),
    )

    conn.commit()
    conn.close()


# ==========================================================
# Update Trade
# ==========================================================

def update_open_trade(current_price):

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute("""

        SELECT

            id,
            signal,
            entry,
            stop_loss,
            target1

        FROM paper_trades

        WHERE status='OPEN'

        LIMIT 1

    """)

    row = cursor.fetchone()

    if row is None:
        conn.close()
        return

    trade_id, signal, entry, stop_loss, target1 = row

    should_close = False
    pnl = 0
    reason = ""

    if signal == "BUY":

        if current_price >= target1:

            pnl = current_price - entry

            should_close = True

            reason = "TARGET"

        elif current_price <= stop_loss:

            pnl = current_price - entry

            should_close = True

            reason = "STOP LOSS"

    elif signal == "SELL":

        if current_price <= target1:

            pnl = entry - current_price

            should_close = True

            reason = "TARGET"

        elif current_price >= stop_loss:

            pnl = entry - current_price

            should_close = True

            reason = "STOP LOSS"

    if should_close:

        cursor.execute("""

            UPDATE paper_trades

            SET

                status='CLOSED',

                exit_price=?,

                pnl=?,

                reason=?,

                duration=

                CAST(

                    (julianday('now')-

                    julianday(timestamp))

                    *24*60

                    AS INTEGER

                ) || ' min'

            WHERE id=?

        """, (

            round(current_price,2),

            round(pnl,2),

            reason,

            trade_id

        ))

        conn.commit()

    conn.close()


# ==========================================================
# Main AI Decision
# ==========================================================

def analyze_trade(snapshot):

    history = snapshot["history"]

    trend = analyze_trend(snapshot)

    sr = calculate_support_resistance(history)

    candle = detect_pattern(history)

    confidence = calculate_confidence(

        trend_result=trend,

        candle_result=candle,

        support_result=sr,

    )

    indicators = snapshot["indicators"].copy()

    indicators["SUPPORT"] = sr["support"]

    indicators["RESISTANCE"] = sr["resistance"]

    risk = calculate_trade_levels(

        indicators,

        confidence["signal"]

    )

    update_open_trade(snapshot["ltp"])

    decision = confidence["signal"]

    result = {

        "decision": decision,

        "confidence": confidence["confidence"],

        "bull_score": confidence["bull_score"],

        "bear_score": confidence["bear_score"],

        "trend": trend,

        "pattern": candle,

        "support_resistance": sr,

        "risk": risk,

        "entry": risk["ENTRY"],

        "stop_loss": risk["STOP_LOSS"],

        "target1": risk["TARGET1"],

        "target2": risk["TARGET2"],

        "reason": confidence["reason"],

    }

    if decision != "HOLD":

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_decision({

            "timestamp": timestamp,

            "symbol": snapshot.get("symbol","NIFTY"),

            "price": snapshot["ltp"],

            "signal": decision,

            "confidence": confidence["confidence"],

            "bull_score": confidence["bull_score"],

            "bear_score": confidence["bear_score"],

            "entry": risk["ENTRY"],

            "stop_loss": risk["STOP_LOSS"],

            "target1": risk["TARGET1"],

            "target2": risk["TARGET2"],

            "support": sr["support"],

            "resistance": sr["resistance"],

            "rsi": indicators["RSI"],

            "adx": indicators["ADX"],

            "atr": indicators["ATR"],

            "ema20": indicators["EMA20"],

            "ema50": indicators["EMA50"],

            "ema200": indicators["EMA200"],

            "macd": indicators["MACD"],

            "macd_signal": indicators["MACD_SIGNAL"]

        })

        save_trade(result)

    return result