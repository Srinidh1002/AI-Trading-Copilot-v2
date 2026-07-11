from unittest.mock import patch

from agents.strategy_agent import StrategyAgent
from models.strategy_state import StrategyState


@patch(
    "agents.strategy_agent.select_strategy"
)
def test_strategy_agent_returns_state(
    mock_selector,
):

    mock_selector.return_value = {
        "strategy": "BREAKOUT",
        "direction": "BULLISH",
        "confidence": 85,
        "decision": "TRADE",
        "bullish_score": 10,
        "bearish_score": 1,
        "confirmations": [
            "Bullish breakout"
        ],
        "risk_flags": [],
        "suitable_strategies": [
            "BREAKOUT"
        ],
    }

    agent = StrategyAgent()

    result = agent.analyse(
        regime={},
        timeframe={},
        technical={},
        candlestick={},
        chart={},
        option={},
    )

    assert isinstance(
        result,
        StrategyState,
    )

    assert result.strategy == "BREAKOUT"
    assert result.direction == "BULLISH"
    assert result.decision == "TRADE"