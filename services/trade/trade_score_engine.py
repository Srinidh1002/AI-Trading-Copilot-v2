"""
Trade Score Engine

Converts institutional score into executable trade quality.
"""

from services.scoring.institutional_scoring_engine import (
    InstitutionalScoringEngine,
)


class TradeScoreEngine:

    def __init__(self):

        self.engine = InstitutionalScoringEngine()

    # -----------------------------------------------------

    def evaluate(
        self,
        snapshot,
        decision,
    ):

        institutional = self.engine.calculate(
            snapshot,
            decision,
        )

        score = institutional["Score"]

        grade = institutional["Grade"]

        if score >= 90:

            action = "EXECUTE"

            risk = "FULL"

        elif score >= 80:

            action = "EXECUTE"

            risk = "HIGH"

        elif score >= 70:

            action = "EXECUTE"

            risk = "MEDIUM"

        elif score >= 60:

            action = "WATCH"

            risk = "LOW"

        else:

            action = "SKIP"

            risk = "NONE"

        return {

            "Score": score,

            "Grade": grade,

            "Action": action,

            "RiskLevel": risk,

            "Reasons": institutional["Reasons"],

        }