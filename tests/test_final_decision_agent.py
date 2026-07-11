from unittest.mock import patch

from agents.final_decision_agent import (
    FinalDecisionAgent,
)

from models.final_decision_state import (
    FinalDecisionState,
)


@patch(
    "agents.final_decision_agent."
    "make_final_decision"
)
def test_final_decision_agent_returns_state(
    mock_engine,
):

    mock_engine.return_value = {
        "decision": "TRADE",
        "action": "BUY_CALL",
        "direction": "BULLISH",
        "strategy": "BREAKOUT",
        "confidence": 85,
        "approved": True,
        "reasons": [
            "Strong setup"
        ],
        "risk_flags": [],
    }

    agent = FinalDecisionAgent()

    result = agent.analyse(
        strategy={},
        core_risk={},
        options_risk={},
    )

    assert isinstance(
        result,
        FinalDecisionState,
    )

    assert result.approved is True
    assert result.action == "BUY_CALL"
    assert result.strategy == "BREAKOUT"