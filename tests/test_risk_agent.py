from unittest.mock import patch

from agents.risk_agent import RiskAgent
from models.risk_state import RiskState


@patch(
    "agents.risk_agent.evaluate_trade_risk"
)
def test_risk_agent_returns_state(
    mock_risk_engine,
):

    mock_risk_engine.return_value = {
        "approved": True,
        "decision": "APPROVED",
        "position_size": 200,
        "risk_amount": 1000.0,
        "risk_reward_ratio": 2.0,
        "reasons": [],
        "warnings": [],
    }

    agent = RiskAgent()

    result = agent.analyse(
        strategy={
            "direction": "BULLISH",
            "decision": "TRADE",
        },
        capital=100000,
        entry_price=100,
        stop_loss=95,
        target_price=110,
    )

    assert isinstance(
        result,
        RiskState,
    )

    assert result.approved is True
    assert result.decision == "APPROVED"
    assert result.position_size == 200