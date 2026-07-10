from models.market_state import MarketState
from services.market_score import Score


class MarketAgent:

    def analyse(self):

        score = Score()

        return MarketState(

            trend=score.trend,

            strength=score.strength,

            momentum=score.momentum,

            volatility=score.volatility,

            confidence=score.confidence,

            reasons=score.reasons,
        )