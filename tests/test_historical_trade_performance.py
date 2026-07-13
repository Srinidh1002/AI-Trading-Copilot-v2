import pytest

from services.historical_trade_performance import (
    HistoricalTradePerformanceEngine,
)


def make_trade(
    *,
    status="CLOSED",
    pnl=100.0,
    direction="BULLISH",
    strategy="TREND_CONTINUATION",
    regime="TRENDING_BULLISH",
    volume_bias="BULLISH",
    volume_spike=True,
    trigger_type="BREAKOUT",
):
    return {
        "status": status,
        "realized_pnl": pnl,
        "direction": direction,
        "metadata": {
            "decision_snapshot": {
                "strategy": strategy,
                "market_regime": regime,
                "direction": direction,
                "volume_bias": volume_bias,
                "volume_spike": volume_spike,
                "trigger_type": trigger_type,
            }
        },
    }


def test_analyses_closed_trades_only():

    engine = (
        HistoricalTradePerformanceEngine(
            minimum_sample_size=2
        )
    )

    result = engine.analyse([
        make_trade(
            pnl=100
        ),
        make_trade(
            pnl=-50
        ),
        make_trade(
            status="OPEN",
            pnl=1000,
        ),
    ])

    overall = result[
        "overall"
    ]

    assert (
        overall["total_trades"]
        == 2
    )

    assert overall["wins"] == 1
    assert overall["losses"] == 1
    assert overall["total_pnl"] == 50.0


def test_calculates_performance_metrics():

    engine = (
        HistoricalTradePerformanceEngine(
            minimum_sample_size=3
        )
    )

    result = engine.analyse([
        make_trade(
            pnl=100
        ),
        make_trade(
            pnl=200
        ),
        make_trade(
            pnl=-100
        ),
    ])

    overall = result[
        "overall"
    ]

    assert (
        overall["total_trades"]
        == 3
    )

    assert overall["wins"] == 2
    assert overall["losses"] == 1

    assert (
        overall["win_rate"]
        == 66.67
    )

    assert (
        overall["total_pnl"]
        == 200.0
    )

    assert (
        overall["average_pnl"]
        == 66.67
    )

    assert (
        overall["expectancy"]
        == 66.67
    )

    assert (
        overall[
            "sufficient_sample"
        ]
        is True
    )


def test_insufficient_sample_is_flagged():

    engine = (
        HistoricalTradePerformanceEngine(
            minimum_sample_size=5
        )
    )

    result = engine.analyse([
        make_trade(
            pnl=100
        ),
        make_trade(
            pnl=100
        ),
    ])

    assert (
        result[
            "overall"
        ][
            "sufficient_sample"
        ]
        is False
    )


def test_groups_by_strategy():

    engine = (
        HistoricalTradePerformanceEngine()
    )

    result = engine.analyse([
        make_trade(
            strategy="BREAKOUT",
            pnl=100,
        ),
        make_trade(
            strategy="BREAKOUT",
            pnl=-50,
        ),
        make_trade(
            strategy="PULLBACK",
            pnl=200,
        ),
    ])

    assert (
        result[
            "by_strategy"
        ][
            "BREAKOUT"
        ][
            "total_trades"
        ]
        == 2
    )

    assert (
        result[
            "by_strategy"
        ][
            "PULLBACK"
        ][
            "total_trades"
        ]
        == 1
    )


def test_groups_by_market_regime():

    engine = (
        HistoricalTradePerformanceEngine()
    )

    result = engine.analyse([
        make_trade(
            regime="TRENDING_BULLISH"
        ),
        make_trade(
            regime="RANGING"
        ),
    ])

    assert (
        "TRENDING_BULLISH"
        in result[
            "by_market_regime"
        ]
    )

    assert (
        "RANGING"
        in result[
            "by_market_regime"
        ]
    )


def test_groups_by_direction():

    engine = (
        HistoricalTradePerformanceEngine()
    )

    result = engine.analyse([
        make_trade(
            direction="BULLISH"
        ),
        make_trade(
            direction="BEARISH"
        ),
    ])

    assert (
        "BULLISH"
        in result[
            "by_direction"
        ]
    )

    assert (
        "BEARISH"
        in result[
            "by_direction"
        ]
    )


def test_groups_by_volume_conditions():

    engine = (
        HistoricalTradePerformanceEngine()
    )

    result = engine.analyse([
        make_trade(
            volume_bias="BULLISH",
            volume_spike=True,
        ),
        make_trade(
            volume_bias="BEARISH",
            volume_spike=False,
        ),
    ])

    assert (
        "BULLISH"
        in result[
            "by_volume_bias"
        ]
    )

    assert (
        "True"
        in result[
            "by_volume_spike"
        ]
    )

    assert (
        "False"
        in result[
            "by_volume_spike"
        ]
    )


def test_finds_similar_closed_trades():

    engine = (
        HistoricalTradePerformanceEngine(
            minimum_sample_size=2
        )
    )

    trades = [
        make_trade(
            pnl=100
        ),
        make_trade(
            pnl=200
        ),
        make_trade(
            strategy="PULLBACK",
            pnl=-100,
        ),
        make_trade(
            status="OPEN",
            pnl=1000,
        ),
    ]

    result = engine.find_similar(
        trades,
        {
            "strategy": (
                "TREND_CONTINUATION"
            ),
            "market_regime": (
                "TRENDING_BULLISH"
            ),
            "direction": "BULLISH",
            "volume_bias": "BULLISH",
            "trigger_type": "BREAKOUT",
        },
    )

    assert (
        result[
            "metrics"
        ][
            "total_trades"
        ]
        == 2
    )

    assert (
        result[
            "metrics"
        ][
            "total_pnl"
        ]
        == 300.0
    )


def test_empty_history_is_safe():

    engine = (
        HistoricalTradePerformanceEngine()
    )

    result = engine.analyse(
        []
    )

    assert (
        result[
            "overall"
        ][
            "total_trades"
        ]
        == 0
    )

    assert (
        result[
            "overall"
        ][
            "win_rate"
        ]
        == 0.0
    )


def test_invalid_minimum_sample_size_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "minimum_sample_size must be "
            "a positive integer"
        ),
    ):
        HistoricalTradePerformanceEngine(
            minimum_sample_size=0
        )


def test_invalid_trade_collection_rejected():

    engine = (
        HistoricalTradePerformanceEngine()
    )

    with pytest.raises(
        ValueError,
        match=(
            "trades must be a list or tuple"
        ),
    ):
        engine.analyse(
            {}
        )


def test_invalid_snapshot_rejected():

    engine = (
        HistoricalTradePerformanceEngine()
    )

    with pytest.raises(
        ValueError,
        match=(
            "decision_snapshot must be "
            "a dictionary"
        ),
    ):
        engine.find_similar(
            [],
            None,
        )