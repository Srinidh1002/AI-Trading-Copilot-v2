"""
Market Guard
"""


class MarketGuard:

    @staticmethod
    def evaluate(
        decision,
        risk,
        validation,
    ):

        level = "RED"

        if validation["TradeAllowed"]:

            if decision["Confidence"] >= 90:

                level = "GREEN"

            elif decision["Confidence"] >= 80:

                level = "LIGHT_GREEN"

            else:

                level = "YELLOW"

        summary = []

        summary.append(f"Session : {validation['Session']}")

        summary.append(f"Action : {decision['Action']}")

        summary.append(f"Confidence : {decision['Confidence']}%")

        summary.append(f"Signal : {decision['SignalStrength']}")

        summary.append(f"PCR : {decision['PCR']}")

        summary.append(f"Risk Reward : {risk['RiskReward']}")

        summary.append(f"Trade Allowed : {validation['TradeAllowed']}")

        return {

            "Level": level,

            "Summary": summary,

            "Reasons": validation["Reasons"],
        }