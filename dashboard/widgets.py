import streamlit as st


def decision_card(decision):
    """
    Displays the final AI BUY / SELL / HOLD decision.
    """

    signal = decision["signal"]

    if signal == "BUY":
        st.success("🟢 BUY")

    elif signal == "SELL":
        st.error("🔴 SELL")

    else:
        st.warning("🟡 HOLD")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Confidence",
        f"{decision['confidence']}%"
    )

    col2.metric(
        "Bull Score",
        decision["bull"]
    )

    col3.metric(
        "Bear Score",
        decision["bear"]
    )


def score_card(title, bull, bear):
    """
    Displays a Bull vs Bear score card.
    """

    st.subheader(title)

    col1, col2 = st.columns(2)

    col1.metric(
        "Bull",
        bull
    )

    col2.metric(
        "Bear",
        bear
    )


def trade_card(trade):
    """
    Displays the recommended trade setup.
    """

    st.subheader("🎯 Trade Setup")

    signal = trade["signal"]

    if signal == "HOLD":
        st.info("No trade recommended.")
        return

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Entry",
            trade["entry"]
        )

        st.metric(
            "Stop Loss",
            trade["stop_loss"]
        )

    with col2:

        st.metric(
            "Target 1",
            trade["target1"]
        )

        st.metric(
            "Target 2",
            trade["target2"]
        )

    st.metric(
        "Risk : Reward",
        f'{trade["risk_reward"]} : 1'
    )