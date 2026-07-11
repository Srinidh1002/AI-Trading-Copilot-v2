"""Unit tests for the technical-agent adapter."""

from unittest.mock import patch

import pandas as pd
import pytest

from agents.technical_agent import TechnicalAgent, TechnicalState


@pytest.fixture
def analyzer_result() -> dict[str, object]:
    """Provide a representative technical-analyzer response."""

    return {
        "trend": "BULLISH",
        "score": 80,
        "confidence": 75,
        "reasons": ["EMA20 is above EMA50."],
        "indicators": {
            "ema20": 101.0,
            "ema50": 99.0,
            "ema200": 95.0,
            "rsi": 62.0,
            "macd": 1.2,
            "signal": 0.8,
            "vwap": 100.0,
            "atr": 2.5,
        },
    }


@pytest.fixture
def technical_state(analyzer_result: dict[str, object]) -> TechnicalState:
    """Run the agent while isolating the technical analyzer."""

    with patch(
        "agents.technical_agent.analyse_technical", return_value=analyzer_result
    ) as mocked_analyzer:
        result = TechnicalAgent().analyse(pd.DataFrame())

    mocked_analyzer.assert_called_once()
    return result


def test_technical_agent_returns_technical_state(
    technical_state: TechnicalState,
) -> None:
    """The agent adapts analysis data to its public state object."""

    assert isinstance(technical_state, TechnicalState)


def test_technical_agent_returns_bounded_confidence(
    technical_state: TechnicalState,
) -> None:
    """Confidence returned by the agent remains a percentage."""

    assert 0 <= technical_state.confidence <= 100


def test_technical_agent_returns_indicators(technical_state: TechnicalState) -> None:
    """The agent preserves the analyzer's indicator payload."""

    assert technical_state.indicators
    assert {"ema20", "ema50", "ema200", "rsi", "macd", "signal", "vwap", "atr"} <= (
        technical_state.indicators.keys()
    )


def test_technical_agent_returns_reasons_list(technical_state: TechnicalState) -> None:
    """The agent returns a populated list of explanatory reasons."""

    assert isinstance(technical_state.reasons, list)
    assert technical_state.reasons
