from unittest.mock import patch

from agents.options_risk_agent import (
    OptionsRiskAgent,
)

from models.options_risk_state import (
    OptionsRiskState,
)


@patch(
    "agents.options_risk_agent."
    "evaluate_options_risk"
)
def test_options_risk_agent_returns_state(
    mock_engine,
):

    mock_engine.return_value = {
        "approved": True,
        "decision": "APPROVED",
        "lots": 2,
        "quantity": 50,
        "premium_exposure": 5000.0,
        "spread_percent": 1.0,
        "reasons": [],
        "warnings": [],
    }

    agent = OptionsRiskAgent()

    result = agent.analyse(
        capital=100000,
        premium=100,
        lot_size=25,
        bid_price=99.5,
        ask_price=100.5,
        volume=5000,
        open_interest=10000,
        iv=25,
        delta=0.55,
        theta=-5,
        days_to_expiry=5,
    )

    assert isinstance(
        result,
        OptionsRiskState,
    )

    assert result.approved is True
    assert result.lots == 2
    assert result.quantity == 50