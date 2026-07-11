from models.market_regime import MarketRegime
from services.market_regime_analyzer import (
    analyse_market_regime,
)


class MarketRegimeAgent:

    def analyse(self, data):

        result = analyse_market_regime(data)

        return MarketRegime(
            primary_regime=result["primary_regime"],
            trend=result["trend"],
            volatility=result["volatility"],
            confidence=result["confidence"],
            score=result["score"],
            metrics=result["metrics"],
            reasons=result["reasons"],
        )