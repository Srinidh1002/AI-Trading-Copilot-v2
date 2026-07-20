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
    Displays the AI Trade Plan.
    """

    st.subheader("🎯 AI Trade Plan")

    decision = trade["decision"]

    if decision == "BUY":
        st.success("🟢 BUY")

    elif decision == "SELL":
        st.error("🔴 SELL")

    else:
        st.warning("🟡 HOLD")

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Current Price",
            trade["current_price"]
        )

        st.metric(
            "Entry",
            trade["entry"]
        )

        st.metric(
            "Stop Loss",
            trade["stop_loss"]
        )

        st.metric(
            "Support",
            trade["support"]
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
            f'1 : {trade["risk_reward"]}'
        )

        st.metric(
            "Resistance",
            trade["resistance"]
        )

    st.divider()

    st.subheader("🧠 AI Reasons")

    for reason in trade["reasons"]:
        st.write(f"✅ {reason}")
def market_overview_card(data):
    """
    Displays available Indian market indices.
    Automatically adapts to whatever indices are returned.
    """

    st.subheader("🇮🇳 Indian Market")

    if not data:
        st.warning("No market overview data available.")
        return

    cols = st.columns(len(data))

    for col, (name, item) in zip(cols, data.items()):

        delta = f"{item['change']} ({item['percent']}%)"

        col.metric(
            label=name,
            value=item["price"],
            delta=delta,
        )  