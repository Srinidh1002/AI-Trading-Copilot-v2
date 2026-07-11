"""Unit tests for the option-agent adapter."""

from unittest.mock import patch

from agents.option_agent import OptionAgent
from models.option_state import OptionState


def test_option_agent_returns_option_state_from_mocked_analyzer() -> None:
    """The agent maps only its public analyzer fields into OptionState."""

    analysis = {
        "pcr": 1.2,
        "support": 25000,
        "resistance": 25200,
        "max_pain": 25100,
        "score": 75,
        "confidence": 70,
        "reasons": ["Fresh put writing exceeds fresh call writing."],
    }
    option_chain = {"records": {"data": []}}

    with patch(
        "agents.option_agent.analyse_option_chain", return_value=analysis
    ) as mocked_analyzer:
        state = OptionAgent().analyse(option_chain)

    mocked_analyzer.assert_called_once_with(option_chain)
    assert isinstance(state, OptionState)
    assert state.pcr == 1.2
    assert state.support == 25000
    assert state.resistance == 25200
    assert state.max_pain == 25100
    assert state.score == 75
    assert state.confidence == 70
    assert state.reasons
