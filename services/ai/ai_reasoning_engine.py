"""
AI Reasoning Engine

Generates institutional reasoning from the final trade decision.
"""


class AIReasoningEngine:

    @staticmethod
    def generate(snapshot, decision):

        reasons = []

        # -------------------------------------------------
        # Trend
        # -------------------------------------------------

        trend = decision.get("trend")

        if trend:
            reasons.append(
                f"Market Trend: {trend}"
            )

        # -------------------------------------------------
        # Option Analysis
        # -------------------------------------------------

        option = snapshot.get(
            "option_analysis",
            {},
        )

        if option:

            flow = option.get(
                "Flow",
                {},
            )

            if flow.get("Flow"):

                reasons.append(
                    flow["Flow"]
                )

            if flow.get("Bias"):

                reasons.append(
                    f"Option Bias: {flow['Bias']}"
                )

            pcr = option.get(
                "PCR",
                {},
            )

            if pcr.get("PCR") is not None:

                reasons.append(
                    f"PCR: {pcr['PCR']}"
                )

            max_pain = option.get(
                "MaxPain",
                {},
            )

            if max_pain.get("MaxPain"):

                reasons.append(
                    f"Max Pain: {max_pain['MaxPain']}"
                )

            greeks = option.get(
                "Greeks",
                {},
            )

            summary = greeks.get(
                "Summary",
                {},
            )

            if summary:

                reasons.append(
                    f"Greeks Bias: {summary.get('Bias','Neutral')}"
                )

                reasons.append(
                    f"IV: {summary.get('AverageIV',0)}%"
                )

        # -------------------------------------------------
        # Decision
        # -------------------------------------------------

        signal = decision.get(
            "signal",
            "HOLD",
        )

        confidence = decision.get(
            "confidence",
            0,
        )

        reasons.append(
            f"Final Decision: {signal}"
        )

        reasons.append(
            f"Confidence: {confidence}%"
        )

        return " | ".join(
            dict.fromkeys(
                reasons
            )
        )