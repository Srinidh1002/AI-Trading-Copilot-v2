import streamlit as st

from dashboard.sidebar import sidebar
from dashboard.charts import price_chart
from dashboard.layout import top_layout, bottom_layout
from dashboard.widgets import (
    decision_card,
    score_card,
    trade_card,
    market_overview_card,
)

from services.market_data import (
    get_stock_data,
    get_chart_data,
)

from services.market_overview import market_overview
from services.technical import technical_score
from services.ai_engine import ai_engine
from services.ai_summary import ai_summary
from services.trade_engine import trade_recommendation


def home():

    # =====================================================
    # Sidebar
    # =====================================================

    symbol, refresh = sidebar()

    # =====================================================
    # Market Data
    # =====================================================

    stock = get_stock_data(symbol)
    history = get_chart_data(symbol)
    overview = market_overview()

    # =====================================================
    # AI Engine
    # =====================================================

    technical = technical_score()

    ai_result = ai_engine(technical)

    trade = trade_recommendation(ai_result)

    # =====================================================
    # Header
    # =====================================================

    st.title("🤖 AI Trading Copilot V2")

    market_overview_card(overview)

    st.divider()

    st.subheader(f"{stock['company']} ({symbol})")

    # =====================================================
    # Price Metrics
    # =====================================================

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Current Price",
        f"{stock['price']} {stock['currency']}",
    )

    col2.metric(
        "Previous Close",
        stock["previous_close"],
    )

    change = round(
        stock["price"] - stock["previous_close"],
        2,
    )

    col3.metric(
        "Day Change",
        change,
    )

    st.divider()

    # =====================================================
    # Main Layout
    # =====================================================

    chart_col, ai_col = top_layout()

    with chart_col:

        st.subheader("📈 Price Chart")

        st.plotly_chart(
            price_chart(history),
            use_container_width=True,
        )

    with ai_col:

        st.subheader("🤖 AI Decision")

        decision_card(ai_result["decision"])

        st.divider()

        trade_card(trade)

    st.divider()

    # =====================================================
    # Score Cards
    # =====================================================

    left, right = bottom_layout()

    with left:

        score_card(
            "📈 Technical Score",
            ai_result["technical"]["bull_score"],
            ai_result["technical"]["bear_score"],
        )

    with right:

        score_card(
            "📊 Option Score",
            ai_result["option"]["bull"],
            ai_result["option"]["bear"],
        )

    st.divider()

    # =====================================================
    # Overall AI Score
    # =====================================================

    st.subheader("🎯 AI Confidence")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Bull Score",
        ai_result["bull_score"],
    )

    c2.metric(
        "Bear Score",
        ai_result["bear_score"],
    )

    c3.metric(
        "Confidence",
        ai_result["confidence"],
    )

    st.divider()

    # =====================================================
    # AI Reasons
    # =====================================================

    st.subheader("🧠 AI Summary")

    summary = ai_summary(ai_result)

    for line in summary:
        st.write(f"• {line}")