import streamlit as st

from dashboard.home import home
from dashboard.live_market_test import live_market_test

st.set_page_config(
    page_title="AI Trading Copilot",
    page_icon="📈",
    layout="wide",
)

page = st.sidebar.selectbox(
    "Select Page",
    [
        "Dashboard",
        "Live Market Test",
    ]
)

if page == "Dashboard":
    home()
else:
    live_market_test()