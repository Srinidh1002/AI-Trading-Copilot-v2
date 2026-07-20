"""
Explanation Engine

Creates human-readable explanations for AI decisions.
"""


def generate_explanation(
    decision,
    confidence,
    risk,
):
    """
    Generate AI explanation.

    Returns
    -------
    str
    """

    signal = decision["signal"]

    explanation = []

    explanation.append(f"Decision: {signal}")

    explanation.append(
        f"Confidence: {confidence['confidence']}% ({confidence['grade']})"
    )

    explanation.append(
        f"Reason: {decision['reason']}"
    )

    explanation.append(
        f"Entry: {risk['entry']}"
    )

    explanation.append(
        f"Stop Loss: {risk['stop_loss']}"
    )

    explanation.append(
        f"Target: {risk['target']}"
    )

    explanation.append(
        f"Risk / Reward: {risk['risk_reward']}:1"
    )

    return "\n".join(explanation)