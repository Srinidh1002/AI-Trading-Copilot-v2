"""
AI Explanation Engine
"""


class AIExplanationEngine:

    @staticmethod
    def explain(decision, risk):

        lines = []

        lines.append(
            f"Decision : {decision['Action']}"
        )

        lines.append(
            f"Confidence : {decision['Confidence']}%"
        )

        lines.append(
            f"Signal Strength : {decision['SignalStrength']}"
        )

        lines.append(
            f"PCR : {decision['PCR']}"
        )

        lines.append(
            f"Support : {decision['Support']}"
        )

        lines.append(
            f"Resistance : {decision['Resistance']}"
        )

        lines.append(
            f"Trading Zone : {decision['TradingZone']}"
        )

        lines.append(
            f"Volatility : {risk['Volatility']}"
        )

        if risk["Entry"] is not None:

            lines.append("")

            lines.append(
                f"Entry : {risk['Entry']}"
            )

            lines.append(
                f"Stop Loss : {risk['StopLoss']}"
            )

            lines.append(
                f"Target 1 : {risk['Target1']}"
            )

            lines.append(
                f"Target 2 : {risk['Target2']}"
            )

            lines.append(
                f"Risk Reward : {risk['RiskReward']}"
            )

        lines.append("")

        lines.append("Reasons:")

        for reason in decision["Reasons"]:

            lines.append(
                f"- {reason}"
            )

        smart = decision["SmartMoney"]

        if smart["Observations"]:

            lines.append("")

            lines.append(
                "Smart Money:"
            )

            for item in smart["Observations"]:

                lines.append(
                    f"- {item}"
                )

        return "\n".join(lines)