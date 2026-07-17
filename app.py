import streamlit as st

from dashboard.home import home
from dashboard.live_market_test import live_market_test

st.set_page_config(
    page_title="AI Trading Copilot",
    page_icon="📈",
    layout="wide",
)

# Temporary during development

live_market_test()