"""
Adaptive Learning Engine

Learns from completed trades and dynamically
adjusts confidence multipliers for the decision engine.
"""

from collections import deque
from statistics import mean


class AdaptiveLearningEngine:

    def __init__(self, max_history=500):

        self.trade_history = deque(maxlen=max_history)

        self.weights = {

            "trend": 1.0,
            "structure": 1.0,
            "candlestick": 1.0,
            "volume": 1.0,
            "market_breadth": 1.0,
            "market_regime": 1.0,
            "liquidity": 1.0,
            "correlation": 1.0,
            "fii_dii": 1.0,
            "vix": 1.0,
            "news": 1.0,
            "economic": 1.0,
            "options": 1.0,
            "greeks": 1.0,
            "smart_money": 1.0,
            "multi_timeframe": 1.0,
        }

    def add_trade(

        self,

        engine_scores: dict,

        pnl: float,

    ):

        self.trade_history.append({

            "engines": engine_scores,

            "pnl": pnl,

        })

        self._recalculate()

    def _recalculate(self):

        if len(self.trade_history) < 20:
            return

        for engine in self.weights.keys():

            winning = []
            losing = []

            for trade in self.trade_history:

                score = trade["engines"].get(
                    engine,
                    0,
                )

                if trade["pnl"] >= 0:

                    winning.append(score)

                else:

                    losing.append(score)

            if not winning or not losing:
                continue

            diff = mean(winning) - mean(losing)

            weight = 1.0 + (diff / 100)

            weight = max(
                0.60,
                min(
                    weight,
                    1.60,
                ),
            )

            self.weights[engine] = round(
                weight,
                2,
            )

    def weighted_score(

        self,

        scores: dict,

    ):

        total = 0
        weight_sum = 0

        for engine, score in scores.items():

            weight = self.weights.get(
                engine,
                1.0,
            )

            total += score * weight

            weight_sum += weight

        if weight_sum == 0:

            return 0

        return round(
            total / weight_sum,
            2,
        )

    def get_weights(self):

        return self.weights.copy()

    def statistics(self):

        if not self.trade_history:

            return {

                "trades": 0,

                "win_rate": 0,

                "average_pnl": 0,

                "weights": self.weights,

            }

        wins = sum(

            1

            for trade in self.trade_history

            if trade["pnl"] > 0

        )

        pnls = [

            trade["pnl"]

            for trade in self.trade_history

        ]

        return {

            "trades": len(
                self.trade_history,
            ),

            "win_rate": round(

                wins

                * 100

                / len(self.trade_history),

                2,

            ),

            "average_pnl": round(

                mean(pnls),

                2,

            ),

            "weights": self.weights.copy(),

        }