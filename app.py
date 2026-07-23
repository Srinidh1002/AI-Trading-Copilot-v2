import streamlit as st

from dashboard.dashboard_v2 import home

from services.database import initialize_database
import services.market.live_multi_timeframe_data as lmtd

# Initialize Database
initialize_database()

# Initialize Session State
if "validation_started" not in st.session_state:
    st.session_state.validation_started = True

if "current_trade_id" not in st.session_state:
    st.session_state.current_trade_id = None

if "last_signal" not in st.session_state:
    st.session_state.last_signal = None

if "trade_open" not in st.session_state:
    st.session_state.trade_open = False

if "dashboard_refresh" not in st.session_state:
    st.session_state.dashboard_refresh = 0

st.set_page_config(
    page_title="AI Trading Copilot",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    footer {visibility:hidden;}
    #MainMenu {visibility:hidden;}
    header {visibility:hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

home()