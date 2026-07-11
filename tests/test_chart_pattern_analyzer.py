import pandas as pd
import pytest

from services.chart_pattern_analyzer import (
    analyse_chart_patterns,
)


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


def test_uptrend_structure():
    data = make_data([
        [100, 105, 95, 102, 1000],
        [102, 107, 97, 104, 1100],
        [104, 109, 99, 106, 1200],
        [106, 111, 101, 108, 1300],
        [108, 113, 103, 110, 1400],
    ])

    result = analyse_chart_patterns(data)

    assert "UPTREND_STRUCTURE" in result["patterns"]
    assert result["signal"] == "BULLISH"


def test_downtrend_structure():
    data = make_data([
        [110, 115, 105, 112, 1000],
        [108, 113, 103, 106, 1100],
        [106, 111, 101, 104, 1200],
        [104, 109, 99, 102, 1300],
        [102, 107, 97, 100, 1400],
    ])

    result = analyse_chart_patterns(data)

    assert "DOWNTREND_STRUCTURE" in result["patterns"]
    assert result["signal"] == "BEARISH"


def test_double_top():
    data = make_data([
        [100, 110, 98, 108, 1000],
        [108, 112, 105, 106, 1000],
        [106, 108, 100, 102, 1000],
        [102, 111.8, 101, 108, 1000],
        [108, 109, 100, 102, 1000],
    ])

    result = analyse_chart_patterns(data)

    assert "DOUBLE_TOP" in result["patterns"]


def test_double_bottom():
    data = make_data([
        [110, 112, 100, 102, 1000],
        [102, 108, 98, 105, 1000],
        [105, 110, 101, 108, 1000],
        [108, 109, 98.2, 103, 1000],
        [103, 110, 101, 108, 1000],
    ])

    result = analyse_chart_patterns(data)

    assert "DOUBLE_BOTTOM" in result["patterns"]


def test_breakout_with_volume_confirmation():
    data = make_data([
        [100, 105, 98, 102, 1000],
        [102, 106, 100, 104, 1000],
        [104, 107, 102, 105, 1000],
        [105, 108, 103, 106, 1000],
        [106, 109, 104, 107, 1000],
        [108, 115, 107, 114, 2000],
    ])

    result = analyse_chart_patterns(data)

    assert "BREAKOUT" in result["patterns"]
    assert result["volume_confirmation"] is True
    assert result["signal"] == "BULLISH"


def test_empty_dataframe():
    result = analyse_chart_patterns(
        pd.DataFrame()
    )

    assert result["signal"] == "NEUTRAL"
    assert result["patterns"] == []


def test_missing_columns():
    data = pd.DataFrame({
        "close": [100, 101]
    })

    with pytest.raises(ValueError):
        analyse_chart_patterns(data)