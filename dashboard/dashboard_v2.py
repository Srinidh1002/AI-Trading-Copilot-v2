import sqlite3

import pandas as pd
import streamlit as st

from services.market_snapshot import get_market_snapshot

from services.trade.trade_engine import analyze_trade

from services.trade.paper_trade_manager import (
    get_trade_statistics,
)

DB = "database/ai_trading.db"


def load_history(limit=25):

    try:
        conn = sqlite3.connect(DB)

        df = pd.read_sql_query(
            """
            SELECT
                timestamp,
                signal,
                confidence,
                price
            FROM decision_log
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )

        conn.close()

        return df

    except Exception:
        return pd.DataFrame()


def load_validation_stats():

    return get_trade_statistics()


def home():

    snapshot = get_market_snapshot()

    trade = analyze_trade(snapshot)

    indicators = snapshot["indicators"]

    stats = load_validation_stats()

    st.title("🤖 AI Trading Copilot V2")

    st.caption(
        f"Market : {snapshot['market_status']} | "
        f"Updated : {snapshot['refresh_time']}"
    )

    st.divider()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("NIFTY", round(snapshot["ltp"], 2))
    c2.metric("Decision", trade["decision"])
    c3.metric("Confidence", f"{trade['confidence']}%")
    c4.metric("Trend", trade["trend"]["trend"])

    st.divider()

    a, b, c, d = st.columns(4)

    a.metric("Bull Score", trade["bull_score"])
    b.metric("Bear Score", trade["bear_score"])
    c.metric("Neutral", trade["neutral_score"])
    d.metric("RSI", round(indicators["RSI"], 2))

    st.divider()

    st.subheader("📊 Trend Analysis")

    x1, x2, x3 = st.columns(3)

    x1.metric("Momentum", trade["trend"]["momentum"])
    x2.metric("Strength", trade["trend"]["strength"])
    x3.metric("Score", f"{trade['trend']['score']}%")

    st.divider()

    st.subheader("🕯 Candlestick")

    y1, y2, y3 = st.columns(3)

    y1.metric("Pattern", trade["pattern"]["pattern"])
    y2.metric("Signal", trade["pattern"]["signal"])
    y3.metric("Status", "Detected")

    st.divider()

    st.subheader("📍 Support & Resistance")

    s1, s2 = st.columns(2)

    s1.metric(
        "Support",
        round(
            trade["support_resistance"]["Support"],
            2,
        ),
    )

    s2.metric(
        "Resistance",
        round(
            trade["support_resistance"]["Resistance"],
            2,
        ),
    )

    st.divider()

    st.subheader("💰 Trade Plan")

    p1, p2, p3 = st.columns(3)

    p1.metric("Entry", trade["entry"])
    p1.metric("Stop Loss", trade["stop_loss"])

    p2.metric("Target 1", trade["target1"])
    p2.metric("Target 2", trade["target2"])

    p3.metric(
        "Target 3",
        trade["risk"]["TARGET3"],
    )

    p3.metric(
        "Risk : Reward",
        trade["risk"]["RR"],
    )

    st.divider()

    st.subheader("🧠 AI Reason")

    st.info(trade["reason"])

    st.divider()

    st.subheader("📈 Validation")

    v1, v2, v3, v4 = st.columns(4)

    v1.metric("Trades", stats["total_trades"])
    v2.metric("Wins", stats["winning_trades"])
    v3.metric("Losses", stats["losing_trades"])
    v4.metric("Net PnL", stats["net_pnl"])

    st.divider()

    st.subheader("📜 Decision History")

    history = load_history()

    if history.empty:
        st.info("No trade history available.")
    else:
        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True,
        )