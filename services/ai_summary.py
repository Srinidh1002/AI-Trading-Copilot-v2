"""
AI Summary Generator
"""


def ai_summary(ai_result):

    technical = ai_result["technical"]
    market = ai_result["market"]
    sentiment = ai_result["sentiment"]
    option = ai_result["option"]
    decision = ai_result["decision"]

    summary = []

    # ------------------------
    # Technical
    # ------------------------

    if technical["bull"] > technical["bear"]:
        summary.append(
            "📈 Technical indicators are bullish."
        )
    else:
        summary.append(
            "📉 Technical indicators are bearish."
        )

    # ------------------------
    # Market
    # ------------------------

    summary.append(
        f"🌍 Market trend: {market['trend']}."
    )

    # ------------------------
    # News
    # ------------------------

    summary.append(
        f"📰 News sentiment: {sentiment['summary']}."
    )

    # ------------------------
    # Option Chain
    # ------------------------

    summary.append(
        f"📊 PCR is {option['PCR']}."
    )

    summary.append(
        f"Support near {option['support']}."
    )

    summary.append(
        f"Resistance near {option['resistance']}."
    )

    # ------------------------
    # Final Decision
    # ------------------------

    summary.append(
        f"🤖 Final AI Signal: {decision['signal']} "
        f"with {decision['confidence']}% confidence."
    )

    return summary