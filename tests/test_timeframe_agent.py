from unittest.mock import patch

from agents.timeframe_agent import TimeframeAgent
from models.timeframe_state import TimeframeState


@patch("agents.timeframe_agent.analyse_multi_timeframe")
def test_timeframe_agent_returns_state(mock_analyse):

    mock_analyse.return_value = {
        "overall_trend": "BULLISH",
        "confidence": 85,
        "alignment": "PARTIAL",
        "timeframe_results": {
            "5m": {"trend": "BULLISH"},
            "15m": {"trend": "BULLISH"},
        },
        "reasons": [
            "5m: BULLISH",
            "15m: BULLISH",
        ],
    }

    agent = TimeframeAgent()

    result = agent.analyse({
        "5m": "mock_data",
        "15m": "mock_data",
    })

    assert isinstance(result, TimeframeState)
    assert result.overall_trend == "BULLISH"
    assert result.confidence == 85
    assert result.alignment == "PARTIAL"