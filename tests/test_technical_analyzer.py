"""Unit tests for the technical-analysis service."""

from collections.abc import Iterator

import pandas as pd
import pytest

from services.technical_analyzer import analyse_technical


@pytest.fixture
def ohlcv_data() -> pd.DataFrame:
    """Provide one valid OHLCV bar for mocked-indicator tests."""

    return pd.DataFrame(
        {
            "Open": [99.0],
            "High": [101.0],
            "Low": [98.0],
            "Close": [100.0],
            "Volume": [1_000],
        }
    )


def _mock_indicators(
    monkeypatch: pytest.MonkeyPatch,
    values: list[float],
) -> None:
    """Make each internal indicator calculation return a known final value."""

    series: Iterator[float] = iter(values)
    monkeypatch.setattr(
        "services.technical_analyzer._calculate",
        lambda _calculation, index: pd.Series(next(series), index=index),
    )


@pytest.mark.parametrize(
    ("indicator_values", "expected_trend", "expected_score"),
    [
        (
            [99.0, 98.0, 97.0, 60.0, 2.0, 1.0, 99.0, 3.0],
            "BULLISH",
            100,
        ),
        (
            [101.0, 102.0, 103.0, 40.0, 1.0, 2.0, 101.0, 3.0],
            "BEARISH",
            0,
        ),
        (
            [99.0, 101.0, 100.0, 60.0, 1.0, 2.0, 101.0, 3.0],
            "SIDEWAYS",
            50,
        ),
    ],
    ids=("bullish_trend", "bearish_trend", "sideways_market"),
)
def test_analyse_technical_classifies_trend(
    monkeypatch: pytest.MonkeyPatch,
    ohlcv_data: pd.DataFrame,
    indicator_values: list[float],
    expected_trend: str,
    expected_score: int,
) -> None:
    """Mocked indicators should deterministically drive trend classification."""

    _mock_indicators(monkeypatch, indicator_values)

    result = analyse_technical(ohlcv_data)

    assert result["trend"] == expected_trend
    assert result["score"] == expected_score
    assert 0 <= result["confidence"] <= 100
    assert result["reasons"]


def test_analyse_technical_rejects_missing_columns() -> None:
    """A useful error is raised when the OHLCV schema is incomplete."""

    incomplete_data = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5]}
    )

    with pytest.raises(ValueError, match="Volume"):
        analyse_technical(incomplete_data)


def test_analyse_technical_handles_empty_dataframe() -> None:
    """An empty but valid OHLCV frame returns a neutral, safe result."""

    empty_data = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    result = analyse_technical(empty_data)

    assert result["trend"] == "SIDEWAYS"
    assert result["score"] == 50
    assert result["confidence"] == 0
    assert result["reasons"] == ["No OHLCV data is available."]
