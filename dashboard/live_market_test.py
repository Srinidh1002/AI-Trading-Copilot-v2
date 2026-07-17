import streamlit as st

from services.market_snapshot import get_market_snapshot


def live_market_test():

    st.title("📈 Live Market Test")

    snapshot = get_market_snapshot()

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("LTP", f"{snapshot['ltp']:.2f}")

    with col2:
        st.metric("Open", f"{snapshot['open']:.2f}")

    with col3:
        st.metric("Close", f"{snapshot['close']:.2f}")

    st.divider()

    col4, col5 = st.columns(2)

    with col4:
        st.metric("High", f"{snapshot['high']:.2f}")

    with col5:
        st.metric("Low", f"{snapshot['low']:.2f}")