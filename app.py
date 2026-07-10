import streamlit as st

from dashboard.home import home

st.set_page_config(
    page_title="AI Trading Copilot",
    page_icon="📈",
    layout="wide"
)

home()