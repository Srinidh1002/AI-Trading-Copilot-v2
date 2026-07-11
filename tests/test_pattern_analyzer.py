import pandas as pd
import pytest

from services.pattern_analyzer import analyse_patterns


def make_data(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )


def test_bullish_engulfing():
    data = make_data([
        [105, 106, 99, 100, 1000],
        [99, 108, 98, 107, 1500],
    ])

    result = analyse_patterns(data)

    assert "BULLISH_ENGULFING" in result["patterns"]
    assert result["signal"] == "BULLISH"


def test_bearish_engulfing():
    data = make_data([
        [100, 106, 99, 105, 1000],
        [106, 107, 98, 99, 1500],
    ])

    result = analyse_patterns(data)

    assert "BEARISH_ENGULFING" in result["patterns"]
    assert result["signal"] == "BEARISH"


def test_empty_dataframe():
    result = analyse_patterns(pd.DataFrame())

    assert result["signal"] == "NEUTRAL"
    assert result["patterns"] == []


def test_missing_columns():
    data = pd.DataFrame({
        "close": [100, 101]
    })

    with pytest.raises(ValueError):
        analyse_patterns(data)


def test_support_and_resistance():
    data = make_data([
        [100, 105, 95, 102, 1000],
        [102, 110, 100, 108, 1200],
        [108, 115, 104, 112, 1300],
    ])

    result = analyse_patterns(data)

    assert result["support"] == 95.0
    assert result["resistance"] == 115.0