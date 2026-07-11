"""Unit tests for the rule-based market analyzer."""

import pytest

from services.market_analyzer import analyse_market


@pytest.mark.parametrize(
    ("indices", "expected"),
    [
        (
            {
                "nifty": {"price": 102.0, "change": 2.0},
                "banknifty": {"price": 102.0, "change": 2.0},
                "vix": {"price": 12.0, "change": 0.0},
            },
            {
                "trend": "BULLISH",
                "strength": 100,
                "momentum": 100,
                "volatility": 40,
                "confidence": 70,
            },
        ),
        (
            {
                "nifty": {"price": 98.0, "change": -2.0},
                "banknifty": {"price": 98.0, "change": -2.0},
                "vix": {"price": 25.0, "change": 0.0},
            },
            {
                "trend": "BEARISH",
                "strength": 100,
                "momentum": 0,
                "volatility": 83,
                "confidence": 30,
            },
        ),
        (
            {
                "nifty": {"price": 100.5, "change": 0.5},
                "banknifty": {"price": 99.5, "change": -0.5},
                "vix": {"price": 17.0, "change": 0.0},
            },
            {
                "trend": "NEUTRAL",
                "strength": 0,
                "momentum": 50,
                "volatility": 57,
                "confidence": 50,
            },
        ),
    ],
    ids=("bullish_market", "bearish_market", "neutral_market"),
)
def test_analyse_market_classifies_market_regimes(
    monkeypatch: pytest.MonkeyPatch,
    indices: dict[str, dict[str, float]],
    expected: dict[str, int | str],
) -> None:
    """Index moves and VIX should produce the expected regime scores."""

    monkeypatch.setattr("services.market_analyzer.market_indices", lambda: indices)

    result = analyse_market()

    for field, value in expected.items():
        assert result[field] == value
    assert result["reasons"]


def test_analyse_market_handles_missing_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """No market payload should return the safe default analysis."""

    monkeypatch.setattr("services.market_analyzer.market_indices", lambda: {})

    result = analyse_market()

    assert result == {
        "trend": "NEUTRAL",
        "strength": 0,
        "volatility": 0,
        "momentum": 0,
        "confidence": 50,
        "reasons": ["No market data is available."],
    }


def test_analyse_market_handles_invalid_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """Malformed index records should not raise or influence scoring."""

    monkeypatch.setattr(
        "services.market_analyzer.market_indices",
        lambda: {
            "nifty": {"price": "unknown", "change": None},
            "banknifty": None,
            "vix": {"price": -1, "change": 0},
        },
    )

    result = analyse_market()

    assert result["trend"] == "NEUTRAL"
    assert result["strength"] == 0
    assert result["momentum"] == 50
    assert result["volatility"] == 0
    assert result["confidence"] == 50
    assert "NIFTY data is unavailable." in result["reasons"]
    assert "BANKNIFTY data is unavailable." in result["reasons"]
    assert "India VIX data is unavailable." in result["reasons"]
