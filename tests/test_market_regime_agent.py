from unittest.mock import patch

from agents.market_regime_agent import (
    MarketRegimeAgent,
)

from models.market_regime import MarketRegime


@patch(
    "agents.market_regime_agent."
    "analyse_market_regime"
)
def test_market_regime_agent(
    mock_analyse,
):

    mock_analyse.return_value = {
        "primary_regime": "TRENDING_BULLISH",
        "trend": "BULLISH",
        "volatility": "NORMAL",
        "confidence": 80,
        "score": 3,
        "metrics": {
            "adx": 35,
            "atr_percent": 1,
            "bb_width_percent": 10,
        },
        "reasons": [
            "Strong bullish trend."
        ],
    }

    agent = MarketRegimeAgent()

    result = agent.analyse(
        "mock_dataframe"
    )

    assert isinstance(
        result,
        MarketRegime,
    )

    assert (
        result.primary_regime
        == "TRENDING_BULLISH"
    )

    assert result.confidence == 80