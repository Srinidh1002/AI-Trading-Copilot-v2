"""
Adaptive Confidence Engine

Adjusts AI confidence dynamically based on
historical trading performance.
"""

from typing import Dict

from services.performance_engine import performance_engine


MIN_MULTIPLIER = 0.80
MAX_MULTIPLIER = 1.20


class AdaptiveConfidenceEngine:

    def __init__(self):
        pass

    def confidence_multiplier(self) -> float:

        report = performance_engine.report()

        win_rate = report["win_rate"]

        if report["performance"] == "NO_DATA":
            return 1.00

        if win_rate >= 80:
            return 1.20

        elif win_rate >= 70:
            return 1.10

        elif win_rate >= 60:
            return 1.05

        elif win_rate >= 50:
            return 1.00

        elif win_rate >= 40:
            return 0.95

        elif win_rate >= 30:
            return 0.90

        return 0.80

    def adjust(
        self,
        confidence: float,
    ) -> float:

        multiplier = self.confidence_multiplier()

        adjusted = confidence * multiplier

        adjusted = max(
            confidence * MIN_MULTIPLIER,
            adjusted,
        )

        adjusted = min(
            confidence * MAX_MULTIPLIER,
            adjusted,
        )

        adjusted = max(
            0.0,
            min(100.0, adjusted),
        )

        return round(adjusted, 2)

    def report(self) -> Dict:

        multiplier = self.confidence_multiplier()

        return {

            "multiplier": multiplier,

            "performance": performance_engine.report(),

        }


adaptive_confidence_engine = AdaptiveConfidenceEngine()