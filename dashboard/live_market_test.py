import streamlit as st

from services.market_snapshot import get_market_snapshot
from services.trend_engine import analyze_trend
from services.trade_engine import analyze_trade


def live_market_test():

    st.title("📈 Live Market Test")

    snapshot = get_market_snapshot()

    trend = analyze_trend(snapshot)
    trade = analyze_trade(snapshot)

    st.divider()

    # ==========================================================
    # Market Snapshot
    # ==========================================================

    st.subheader("Market Snapshot")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("LTP", f"{snapshot['ltp']:.2f}")

    with col2:
        st.metric("Open", f"{snapshot['open']:.2f}")

    with col3:
        st.metric("Close", f"{snapshot['close']:.2f}")

    col4, col5 = st.columns(2)

    with col4:
        st.metric("High", f"{snapshot['high']:.2f}")

    with col5:
        st.metric("Low", f"{snapshot['low']:.2f}")

    st.divider()

    # ==========================================================
    # Session
    # ==========================================================

    st.subheader("Session")

    c1, c2 = st.columns(2)

    with c1:
        st.metric("Market Status", snapshot["market_status"])

    with c2:
        st.metric("Volume", f"{snapshot['volume']:,}")

    c3, c4 = st.columns(2)

    with c3:
        st.metric("Last Candle", snapshot["candle_time"])

    with c4:
        st.metric("Last Refresh", snapshot["refresh_time"])

    st.divider()

    # ==========================================================
    # Technical Indicators
    # ==========================================================

    st.subheader("Technical Indicators")

    indicators = snapshot["indicators"]

    i1, i2, i3, i4 = st.columns(4)

    with i1:
        st.metric("EMA20", f"{indicators['EMA20']:.2f}")

    with i2:
        st.metric("EMA50", f"{indicators['EMA50']:.2f}")

    with i3:
        st.metric("EMA200", f"{indicators['EMA200']:.2f}")

    with i4:
        st.metric("RSI", f"{indicators['RSI']:.2f}")

    st.divider()

    # ==========================================================
    # Trend Analysis
    # ==========================================================

    st.subheader("📈 Trend Analysis")

    t1, t2, t3 = st.columns(3)

    with t1:
        st.metric("Trend", trend["trend"])

    with t2:
        st.metric("Strength", trend["strength"])

    with t3:
        st.metric("Momentum", trend["momentum"])

    st.divider()

    # ==========================================================
    # Trade Decision
    # ==========================================================

    st.subheader("🎯 Trade Decision")

    d1, d2, d3 = st.columns(3)

    with d1:
        st.metric("Decision", trade["decision"])

    with d2:
        st.metric("Trend", trade["trend"])

    with d3:
        st.metric("Strength", trade["strength"])