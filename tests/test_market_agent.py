"""Unit tests for the market-agent adapter."""

from unittest.mock import patch

import pytest

from agents.market_agent import MarketAgent
from models.market_state import MarketState


@pytest.fixture
def analyzer_result() -> dict[str, int | str | list[str]]:
    """Provide a representative, valid analyzer payload."""

    return {
        "trend": "BULLISH",
        "strength": 80,
        "volatility": 25,
        "momentum": 75,
        "confidence": 70,
        "reasons": ["NIFTY is up 1.25%, adding bullish momentum."],
    }


@pytest.fixture
def market_state(
    analyzer_result: dict[str, int | str | list[str]],
) -> MarketState:
    """Return the agent output while isolating the market analyzer."""

    with patch(
        "agents.market_agent.analyse_market", return_value=analyzer_result
    ) as mocked_analyzer:
        result = MarketAgent().analyse()

    mocked_analyzer.assert_called_once_with()
    return result


def test_market_agent_returns_market_state(market_state: MarketState) -> None:
    """The agent must adapt analyzer data into the domain model."""

    assert isinstance(market_state, MarketState)


def test_market_agent_returns_bounded_confidence(market_state: MarketState) -> None:
    """Confidence exposed by the agent must remain a percentage."""

    assert 0 <= market_state.confidence <= 100


def test_market_agent_returns_populated_reasons(market_state: MarketState) -> None:
    """The agent should preserve the analyzer's explanation."""

    assert market_state.reasons


def test_market_agent_returns_valid_trend(market_state: MarketState) -> None:
    """The agent should expose only supported market trends."""

    assert market_state.trend in {"BULLISH", "BEARISH", "NEUTRAL"}
