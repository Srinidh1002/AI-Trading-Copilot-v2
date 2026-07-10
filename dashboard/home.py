import streamlit as st

from dashboard.sidebar import sidebar
from dashboard.charts import price_chart
from dashboard.widgets import (
    decision_card,
    score_card,
    trade_card,
)
from dashboard.layout import (
    top_layout,
    bottom_layout,
)

from services.market_data import (
    get_stock_data,
    get_chart_data,
)
from dashboard.widgets import (
    decision_card,
    score_card,
    market_overview_card,
)
from services.market_overview import market_overview
from services.technical import calculate_indicators
from services.technical_score import technical_score
from services.ai_engine import ai_engine
from services.ai_summary import ai_summary
from services.trade_engine import trade_recommendation


def home():

    # ====================================================
    # Sidebar
    # ====================================================

    symbol, refresh = sidebar()

    # ====================================================
    # Market Data
    # ====================================================

    stock = get_stock_data(symbol)
    history = get_chart_data(symbol)
    overview = market_overview()
    # ====================================================
    # Technical Analysis
    # ====================================================

    df = history.copy()
    df = calculate_indicators(df)

    technical = technical_score(df)

    # ====================================================
    # AI Engine
    # ====================================================

    ai_result = ai_engine(technical)

    # ====================================================
    # Trade Recommendation
    # ====================================================

    trade = trade_recommendation(
        stock["price"],
        ai_result["decision"]
    )

    # ====================================================
    # Header
    # ====================================================

    st.title("📈 AI Trading Copilot")
    market_overview_card(overview)

    st.divider()
    st.write(f"### {stock['company']} ({symbol})")

    st.divider()

    # ====================================================
    # Price Metrics
    # ====================================================

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Current Price",
        f"{stock['price']} {stock['currency']}"
    )

    col2.metric(
        "Previous Close",
        stock["previous_close"]
    )

    change = round(
        stock["price"] - stock["previous_close"],
        2
    )

    col3.metric(
        "Day Change",
        change
    )

    st.divider()

    # ====================================================
    # Market Information
    # ====================================================

    col4, col5, col6 = st.columns(3)

    col4.metric(
        "Exchange",
        stock["exchange"]
    )

    col5.metric(
        "Currency",
        stock["currency"]
    )

    col6.metric(
        "Symbol",
        symbol
    )

    st.divider()

    # ====================================================
    # Main Dashboard Layout
    # ====================================================

    chart_col, ai_col = top_layout()

    with chart_col:

        st.subheader("📈 Candlestick Chart")

        st.plotly_chart(
            price_chart(history),
            use_container_width=True
        )

    with ai_col:

        st.subheader("🤖 AI Decision")

        decision_card(
            ai_result["decision"]
        )

        st.divider()

        trade_card(trade)

    st.divider()

    # ====================================================
    # Technical & Options
    # ====================================================

    left, right = bottom_layout()

    with left:

        score_card(
            "📈 Technical Analysis",
            ai_result["technical"]["bull"],
            ai_result["technical"]["bear"],
        )

    with right:

        score_card(
            "📊 Option Chain",
            ai_result["option"]["bull"],
            ai_result["option"]["bear"],
        )

    st.divider()

    # ====================================================
    # AI Summary
    # ====================================================

    st.header("🧠 AI Summary")

    summary = ai_summary(ai_result)

    for line in summary:
        st.write(f"• {line}")