"""
Trade Validator
"""

from services.execution.trading_session_engine import TradingSessionEngine


class TradeValidator:

    @staticmethod
    def validate(
        decision,
        risk,
    ):

        reasons = []

        allowed = True

        session = TradingSessionEngine.get_session()

        if not TradingSessionEngine.trading_allowed():

            allowed = False
            reasons.append(f"Market Session : {session}")

        if decision["Action"] == "HOLD":

            allowed = False
            reasons.append("Decision is HOLD")

        if decision["Confidence"] < 70:

            allowed = False
            reasons.append("Confidence below 70%")

        if decision["SignalStrength"] < 4:

            allowed = False
            reasons.append("Weak market signal")

        if risk["RiskReward"] is not None:

            if risk["RiskReward"] < 2:

                allowed = False
                reasons.append("Risk Reward below 1:2")

        return {

            "TradeAllowed": allowed,

            "Session": session,

            "Reasons": reasons,
        }