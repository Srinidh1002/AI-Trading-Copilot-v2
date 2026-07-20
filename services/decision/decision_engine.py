"""
Decision Engine V2
"""

from services.options.oi_engine import OIEngine
from services.options.max_pain_engine import MaxPainEngine


class DecisionEngine:

    @staticmethod
    def analyze(option_chain):

        oi = OIEngine.analyze(option_chain["quotes"])

        pain = MaxPainEngine.analyze(option_chain)

        score = 0

        reasons = []

        # PCR

        if pain["PCR"] > 1.2:
            score += 2
            reasons.append("Bullish PCR")

        elif pain["PCR"] < 0.8:
            score -= 2
            reasons.append("Bearish PCR")

        # OI Bias

        if oi["Bias"] == "Bullish":
            score += 2
            reasons.append("Bullish OI")

        elif oi["Bias"] == "Bearish":
            score -= 2
            reasons.append("Bearish OI")

        # Final Decision

        if score >= 2:

            decision = "BUY"

        elif score <= -2:

            decision = "SELL"

        else:

            decision = "HOLD"

        return {

            "Decision": decision,

            "Score": score,

            "Reasons": reasons,

            "Support": pain["Support"],

            "Resistance": pain["Resistance"],

            "MaxPain": pain["MaxPain"],

            "PCR": pain["PCR"],

            "OI": oi,

        }