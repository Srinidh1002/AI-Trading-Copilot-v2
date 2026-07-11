from services.strategy_selector import (
    select_strategy,
)


def test_bullish_trend_continuation():

    result = select_strategy(
        regime={
            "primary_regime": "TRENDING_BULLISH",
            "trend": "BULLISH",
        },
        timeframe={
            "overall_trend": "BULLISH",
            "alignment": "FULL",
        },
        technical={
            "trend": "BULLISH",
        },
        candlestick={
            "patterns": [
                "BULLISH_ENGULFING"
            ],
        },
        chart={
            "patterns": [
                "UPTREND_STRUCTURE"
            ],
            "volume_confirmation": True,
        },
        option={
            "trend": "BULLISH",
        },
    )

    assert (
        result["strategy"]
        == "TREND_CONTINUATION"
    )

    assert result["direction"] == "BULLISH"
    assert result["decision"] == "TRADE"


def test_bullish_breakout():

    result = select_strategy(
        regime={
            "primary_regime": "COMPRESSION",
            "trend": "NEUTRAL",
        },
        timeframe={
            "overall_trend": "BULLISH",
            "alignment": "PARTIAL",
        },
        technical={
            "trend": "BULLISH",
        },
        candlestick={
            "patterns": [],
        },
        chart={
            "patterns": [
                "BREAKOUT"
            ],
            "volume_confirmation": True,
        },
        option={
            "trend": "BULLISH",
        },
    )

    assert result["strategy"] == "BREAKOUT"
    assert result["direction"] == "BULLISH"
    assert result["decision"] == "TRADE"


def test_bearish_breakdown():

    result = select_strategy(
        regime={
            "primary_regime": "RANGING",
            "trend": "NEUTRAL",
        },
        timeframe={
            "overall_trend": "BEARISH",
            "alignment": "PARTIAL",
        },
        technical={
            "trend": "BEARISH",
        },
        candlestick={
            "patterns": [],
        },
        chart={
            "patterns": [
                "BREAKDOWN"
            ],
            "volume_confirmation": True,
        },
        option={
            "trend": "BEARISH",
        },
    )

    assert result["strategy"] == "BREAKDOWN"
    assert result["direction"] == "BEARISH"
    assert result["decision"] == "TRADE"


def test_conflicting_timeframes_no_trade():

    result = select_strategy(
        regime={
            "primary_regime": "TRENDING_BULLISH",
            "trend": "BULLISH",
        },
        timeframe={
            "overall_trend": "MIXED",
            "alignment": "CONFLICTED",
        },
        technical={
            "trend": "BULLISH",
        },
        candlestick={
            "patterns": [],
        },
        chart={
            "patterns": [],
            "volume_confirmation": False,
        },
        option={
            "trend": "BEARISH",
        },
    )

    assert result["decision"] == "NO_TRADE"


def test_neutral_market_no_trade():

    result = select_strategy(
        regime={
            "primary_regime": "UNCERTAIN",
            "trend": "NEUTRAL",
        },
        timeframe={
            "overall_trend": "MIXED",
            "alignment": "CONFLICTED",
        },
        technical={
            "trend": "NEUTRAL",
        },
        candlestick={
            "patterns": [],
        },
        chart={
            "patterns": [],
            "volume_confirmation": False,
        },
        option=None,
    )

    assert result["strategy"] == "NO_TRADE"
    assert result["decision"] == "NO_TRADE"