from models.strategy_state import StrategyState
from services.strategy_selector import (
    select_strategy,
)


class StrategyAgent:

    def analyse(
        self,
        regime,
        timeframe,
        technical,
        candlestick,
        chart,
        option=None,
    ):

        result = select_strategy(
            regime=regime,
            timeframe=timeframe,
            technical=technical,
            candlestick=candlestick,
            chart=chart,
            option=option,
        )

        return StrategyState(
            strategy=result["strategy"],
            direction=result["direction"],
            confidence=result["confidence"],
            decision=result["decision"],
            bullish_score=result[
                "bullish_score"
            ],
            bearish_score=result[
                "bearish_score"
            ],
            confirmations=result[
                "confirmations"
            ],
            risk_flags=result[
                "risk_flags"
            ],
            suitable_strategies=result[
                "suitable_strategies"
            ],
        )