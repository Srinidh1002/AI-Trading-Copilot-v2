import streamlit as st

from config import DEFAULT_SYMBOL


def sidebar():

    st.sidebar.title("🤖 AI Trading Copilot")

    symbol = st.sidebar.text_input(
        "Stock Symbol",
        DEFAULT_SYMBOL
    )

    refresh = st.sidebar.button("🔄 Refresh")

    return symbol, refresh