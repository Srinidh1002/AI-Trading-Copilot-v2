"""
Master AI Decision Engine
"""

from services.market_engine import market_score
from services.sentiment import sentiment_score
from services.option_ai import option_score
from services.strategy_engine import strategy_engine


def ai_engine(technical):

    market = market_score()

    sentiment = sentiment_score()

    option = option_score()

    decision = strategy_engine(
        technical=technical,
        market=market,
        option=option,
        sentiment=sentiment,
    )

    return {
        "technical": technical,
        "market": market,
        "sentiment": sentiment,
        "option": option,
        "decision": decision,
    }