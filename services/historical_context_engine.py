"""
Historical context engine.

Compares the current live decision snapshot with similar CLOSED
paper trades and converts historical performance into a bounded,
descriptive context signal.

IMPORTANT:
- Historical context is advisory only.
- It does not place orders.
- It does not override live market safety gates.
- Insufficient samples must fail closed as INSUFFICIENT_DATA.
"""

from services.historical_trade_performance import (
    HistoricalTradePerformanceEngine,
)


VALID_HISTORICAL_BIASES = {
    "SUPPORTIVE",
    "CAUTION",
    "NEGATIVE",
    "INSUFFICIENT_DATA",
}


class HistoricalContextEngine:

    def __init__(
        self,
        performance_engine=None,
        minimum_sample_size=5,
        supportive_win_rate=60.0,
        negative_win_rate=40.0,
    ):
        if (
            not isinstance(
                minimum_sample_size,
                int,
            )
            or isinstance(
                minimum_sample_size,
                bool,
            )
            or minimum_sample_size < 1
        ):
            raise ValueError(
                "minimum_sample_size must be a positive integer."
            )

        if not (
            0.0
            <= negative_win_rate
            <= supportive_win_rate
            <= 100.0
        ):
            raise ValueError(
                "Historical win-rate thresholds are invalid."
            )

        self.minimum_sample_size = (
            minimum_sample_size
        )

        self.supportive_win_rate = float(
            supportive_win_rate
        )

        self.negative_win_rate = float(
            negative_win_rate
        )

        self.performance_engine = (
            performance_engine
            if performance_engine is not None
            else HistoricalTradePerformanceEngine(
                minimum_sample_size=(
                    minimum_sample_size
                )
            )
        )

    def evaluate(
        self,
        trades,
        decision_snapshot,
    ):
        """
        Evaluate historical context for the current live setup.
        """

        if not isinstance(
            decision_snapshot,
            dict,
        ):
            raise ValueError(
                "decision_snapshot must be a dictionary."
            )

        similar_result = (
            self.performance_engine.find_similar(
                trades=trades,
                decision_snapshot=decision_snapshot,
            )
        )

        metrics = (
            similar_result.get(
                "metrics",
                {},
            )
            or {}
        )

        matching_fields = (
            similar_result.get(
                "matching_fields",
                {},
            )
            or {}
        )

        total_trades = int(
            metrics.get(
                "total_trades",
                0,
            )
            or 0
        )

        win_rate = float(
            metrics.get(
                "win_rate",
                0.0,
            )
            or 0.0
        )

        expectancy = float(
            metrics.get(
                "expectancy",
                0.0,
            )
            or 0.0
        )

        sufficient_sample = (
            total_trades
            >= self.minimum_sample_size
        )

        if not sufficient_sample:

            historical_bias = (
                "INSUFFICIENT_DATA"
            )

            reason = (
                "Not enough similar closed paper trades "
                "are available for reliable historical context."
            )

        elif (
            win_rate
            >= self.supportive_win_rate
            and expectancy > 0
        ):

            historical_bias = (
                "SUPPORTIVE"
            )

            reason = (
                "Similar historical setups show both "
                "a strong win rate and positive expectancy."
            )

        elif (
            win_rate
            <= self.negative_win_rate
            or expectancy < 0
        ):

            historical_bias = (
                "NEGATIVE"
            )

            reason = (
                "Similar historical setups show weak "
                "performance or negative expectancy."
            )

        else:

            historical_bias = (
                "CAUTION"
            )

            reason = (
                "Similar historical setups have mixed "
                "or inconclusive performance."
            )

        return {
            "historical_bias": historical_bias,
            "similar_trades": total_trades,
            "win_rate": round(
                win_rate,
                2,
            ),
            "expectancy": round(
                expectancy,
                2,
            ),
            "total_pnl": metrics.get(
                "total_pnl",
                0.0,
            ),
            "average_pnl": metrics.get(
                "average_pnl",
                0.0,
            ),
            "sufficient_sample": (
                sufficient_sample
            ),
            "minimum_sample_size": (
                self.minimum_sample_size
            ),
            "matching_fields": dict(
                matching_fields
            ),
            "reason": reason,
            "advisory_only": True,
            "can_override_live_safety": False,
        }