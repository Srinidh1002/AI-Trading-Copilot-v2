from models.market_state import MarketState
from services.market_analyzer import analyse_market


class MarketAgent:
    """Adapt market-analyzer output into the domain market-state model."""

    def analyse(self) -> MarketState:
        """Return the current analysed market state."""

        analysis = analyse_market()

        return MarketState(
            trend=analysis["trend"],
            strength=analysis["strength"],
            momentum=analysis["momentum"],
            volatility=analysis["volatility"],
            confidence=analysis["confidence"],
            reasons=analysis["reasons"],
        )
