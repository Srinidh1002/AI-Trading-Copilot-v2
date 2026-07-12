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

    result = analyse_chart_patterns(
        data
    )

    assert (
        "UPTREND_STRUCTURE"
        in result["patterns"]
    )

    assert (
        result["signal"]
        == "BULLISH"
    )


def test_downtrend_structure():

    data = make_data([
        [110, 115, 105, 112, 1000],
        [108, 113, 103, 106, 1100],
        [106, 111, 101, 104, 1200],
        [104, 109, 99, 102, 1300],
        [102, 107, 97, 100, 1400],
    ])

    result = analyse_chart_patterns(
        data
    )

    assert (
        "DOWNTREND_STRUCTURE"
        in result["patterns"]
    )

    assert (
        result["signal"]
        == "BEARISH"
    )


def test_double_top():

    data = make_data([
        [100, 110, 98, 108, 1000],
        [108, 112, 105, 106, 1000],
        [106, 108, 100, 102, 1000],
        [102, 111.8, 101, 108, 1000],
        [108, 109, 100, 102, 1000],
    ])

    result = analyse_chart_patterns(
        data
    )

    assert (
        "DOUBLE_TOP"
        in result["patterns"]
    )


def test_double_bottom():

    data = make_data([
        [110, 112, 100, 102, 1000],
        [102, 108, 98, 105, 1000],
        [105, 110, 101, 108, 1000],
        [108, 109, 98.2, 103, 1000],
        [103, 110, 101, 108, 1000],
    ])

    result = analyse_chart_patterns(
        data
    )

    assert (
        "DOUBLE_BOTTOM"
        in result["patterns"]
    )


def test_breakout_with_volume_confirmation():

    data = make_data([
        [100, 105, 98, 102, 1000],
        [102, 106, 100, 104, 1000],
        [104, 107, 102, 105, 1000],
        [105, 108, 103, 106, 1000],
        [106, 109, 104, 107, 1000],
        [108, 115, 107, 114, 2000],
    ])

    result = analyse_chart_patterns(
        data
    )

    assert (
        "BREAKOUT"
        in result["patterns"]
    )

    assert (
        result[
            "volume_confirmation"
        ]
        is True
    )

    assert (
        result["signal"]
        == "BULLISH"
    )


def test_empty_dataframe():

    result = analyse_chart_patterns(
        pd.DataFrame()
    )

    assert (
        result["signal"]
        == "NEUTRAL"
    )

    assert (
        result["patterns"]
        == []
    )


def test_missing_columns():

    data = pd.DataFrame({
        "close": [
            100,
            101,
        ]
    })

    with pytest.raises(
        ValueError
    ):
        analyse_chart_patterns(
            data
        )


def test_does_not_return_both_double_top_and_bottom():

    data = make_data([
        [100, 110, 90, 100, 1000],
        [100, 112, 92, 105, 1000],
        [105, 108, 88, 95, 1000],
        [95, 111.8, 92, 105, 1000],
        [105, 108, 88.2, 100, 1000],
        [100, 109, 94, 102, 1000],
    ])

    result = analyse_chart_patterns(
        data
    )

    has_double_top = (
        "DOUBLE_TOP"
        in result["patterns"]
    )

    has_double_bottom = (
        "DOUBLE_BOTTOM"
        in result["patterns"]
    )

    assert not (
        has_double_top
        and has_double_bottom
    )


def test_conflict_resolution_is_reported():

    data = make_data([
        [100, 110, 90, 100, 1000],
        [100, 112, 92, 105, 1000],
        [105, 108, 88, 95, 1000],
        [95, 111.8, 92, 105, 1000],
        [105, 108, 88.2, 100, 1000],
        [100, 109, 94, 102, 1000],
    ])

    result = analyse_chart_patterns(
        data
    )

    assert (
        result[
            "pattern_conflict_resolved"
        ]
        is True
    )


def test_consolidation_does_not_create_false_reversal_conflict():

    data = make_data([
        [100, 101, 99, 100.2, 1000],
        [100.2, 101.1, 99.2, 100.5, 1000],
        [100.5, 100.9, 99.4, 100.1, 1000],
        [100.1, 101.0, 99.3, 100.4, 1000],
        [100.4, 100.8, 99.5, 100.2, 1000],
        [100.2, 100.9, 99.4, 100.3, 1000],
    ])

    result = analyse_chart_patterns(
        data
    )

    assert (
        "CONSOLIDATION"
        in result["patterns"]
    )

    assert not (
        "DOUBLE_TOP"
        in result["patterns"]
        and
        "DOUBLE_BOTTOM"
        in result["patterns"]
    )


def test_reversal_pattern_output_is_directionally_consistent():

    data = make_data([
        [100, 110, 95, 105, 1000],
        [105, 112, 100, 106, 1000],
        [106, 108, 98, 101, 1000],
        [101, 111.9, 99, 105, 1000],
        [105, 108, 97, 100, 1000],
    ])

    result = analyse_chart_patterns(
        data
    )

    assert not (
        "DOUBLE_TOP"
        in result["patterns"]
        and
        "DOUBLE_BOTTOM"
        in result["patterns"]
    )