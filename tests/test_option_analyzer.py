"""Unit tests for option-chain analysis."""

import pytest

from services.option_analyzer import analyse_options


def _chain(rows: list[dict[str, object]]) -> dict[str, object]:
    """Wrap test rows in the NSE response shape used by the analyzer."""

    return {"records": {"data": rows}}


@pytest.mark.parametrize(
    ("rows", "expected_score", "expected_pcr", "expected_support", "expected_resistance"),
    [
        (
            [
                {
                    "strikePrice": 100,
                    "CE": {"openInterest": 100, "changeinOpenInterest": 10},
                    "PE": {"openInterest": 500, "changeinOpenInterest": 100},
                },
                {
                    "strikePrice": 110,
                    "CE": {"openInterest": 300, "changeinOpenInterest": 20},
                    "PE": {"openInterest": 300, "changeinOpenInterest": 50},
                },
            ],
            75,
            2.0,
            100,
            110,
        ),
        (
            [
                {
                    "strikePrice": 100,
                    "CE": {"openInterest": 500, "changeinOpenInterest": 100},
                    "PE": {"openInterest": 100, "changeinOpenInterest": 10},
                },
                {
                    "strikePrice": 110,
                    "CE": {"openInterest": 300, "changeinOpenInterest": 50},
                    "PE": {"openInterest": 300, "changeinOpenInterest": 10},
                },
            ],
            25,
            0.5,
            110,
            100,
        ),
        (
            [
                {
                    "strikePrice": 100,
                    "CE": {"openInterest": 300, "changeinOpenInterest": 40},
                    "PE": {"openInterest": 200, "changeinOpenInterest": 20},
                },
                {
                    "strikePrice": 110,
                    "CE": {"openInterest": 200, "changeinOpenInterest": 10},
                    "PE": {"openInterest": 300, "changeinOpenInterest": 30},
                },
            ],
            50,
            1.0,
            110,
            100,
        ),
    ],
    ids=("bullish_option_chain", "bearish_option_chain", "neutral_option_chain"),
)
def test_analyse_options_scores_market_sentiment(
    rows: list[dict[str, object]],
    expected_score: int,
    expected_pcr: float,
    expected_support: int,
    expected_resistance: int,
) -> None:
    """PCR and fresh writing should produce deterministic sentiment scores."""

    result = analyse_options(_chain(rows))

    assert result["score"] == expected_score
    assert result["pcr"] == expected_pcr
    assert result["support"] == expected_support
    assert result["resistance"] == expected_resistance
    assert 0 <= result["confidence"] <= 100
    assert result["reasons"]


def test_analyse_options_handles_empty_data() -> None:
    """An empty NSE payload produces a safe neutral response."""

    result = analyse_options(_chain([]))

    assert result["score"] == 50
    assert result["confidence"] == 0
    assert result["reasons"] == ["No valid option-chain strikes are available."]


def test_analyse_options_ignores_rows_without_strikes() -> None:
    """Rows lacking a usable strike are treated as unavailable data."""

    result = analyse_options(
        _chain([{"CE": {"openInterest": 100}, "PE": {"openInterest": 100}}])
    )

    assert result["support"] == 0
    assert result["resistance"] == 0
    assert result["max_pain"] == 0
    assert result["score"] == 50


def test_analyse_options_handles_invalid_pcr_when_call_oi_is_zero() -> None:
    """A zero call-OI denominator must not raise or return infinity."""

    result = analyse_options(
        _chain(
            [
                {
                    "strikePrice": 100,
                    "CE": {"openInterest": 0, "changeinOpenInterest": 0},
                    "PE": {"openInterest": 200, "changeinOpenInterest": 0},
                }
            ]
        )
    )

    assert result["pcr"] == 0.0
    assert result["score"] == 50
    assert "PCR is set to 0.0." in result["reasons"][0]
