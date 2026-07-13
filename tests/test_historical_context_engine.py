import pytest

from services.historical_context_engine import (
    HistoricalContextEngine,
)


def make_trade(
    *,
    pnl=100.0,
    status="CLOSED",
    strategy="TREND_CONTINUATION",
    regime="TRENDING_BULLISH",
    direction="BULLISH",
    volume_bias="BULLISH",
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
                "trigger_type": trigger_type,
            }
        },
    }


def current_snapshot():
    return {
        "strategy": "TREND_CONTINUATION",
        "market_regime": "TRENDING_BULLISH",
        "direction": "BULLISH",
        "volume_bias": "BULLISH",
        "trigger_type": "BREAKOUT",
    }


def test_supportive_historical_context():

    engine = HistoricalContextEngine(
        minimum_sample_size=5
    )

    trades = [
        make_trade(pnl=100),
        make_trade(pnl=120),
        make_trade(pnl=80),
        make_trade(pnl=150),
        make_trade(pnl=-50),
    ]

    result = engine.evaluate(
        trades,
        current_snapshot(),
    )

    assert (
        result["historical_bias"]
        == "SUPPORTIVE"
    )

    assert result["similar_trades"] == 5
    assert result["win_rate"] == 80.0
    assert result["expectancy"] > 0
    assert result["sufficient_sample"] is True


def test_negative_historical_context():

    engine = HistoricalContextEngine(
        minimum_sample_size=5
    )

    trades = [
        make_trade(pnl=-100),
        make_trade(pnl=-80),
        make_trade(pnl=-120),
        make_trade(pnl=-50),
        make_trade(pnl=40),
    ]

    result = engine.evaluate(
        trades,
        current_snapshot(),
    )

    assert (
        result["historical_bias"]
        == "NEGATIVE"
    )

    assert result["win_rate"] == 20.0
    assert result["expectancy"] < 0


def test_negative_when_expectancy_is_negative():

    engine = HistoricalContextEngine(
        minimum_sample_size=5
    )

    trades = [
        make_trade(pnl=20),
        make_trade(pnl=20),
        make_trade(pnl=20),
        make_trade(pnl=-200),
        make_trade(pnl=-200),
    ]

    result = engine.evaluate(
        trades,
        current_snapshot(),
    )

    assert (
        result["historical_bias"]
        == "NEGATIVE"
    )

    assert result["expectancy"] < 0


def test_caution_for_mixed_history():

    engine = HistoricalContextEngine(
        minimum_sample_size=5
    )

    trades = [
        make_trade(pnl=100),
        make_trade(pnl=100),
        make_trade(pnl=100),
        make_trade(pnl=-50),
        make_trade(pnl=-50),
        make_trade(pnl=-50),
    ]

    result = engine.evaluate(
        trades,
        current_snapshot(),
    )

    assert (
        result["historical_bias"]
        == "CAUTION"
    )

    assert result["win_rate"] == 50.0
    assert result["expectancy"] > 0


def test_insufficient_data_fails_closed():

    engine = HistoricalContextEngine(
        minimum_sample_size=5
    )

    trades = [
        make_trade(pnl=100),
        make_trade(pnl=100),
    ]

    result = engine.evaluate(
        trades,
        current_snapshot(),
    )

    assert (
        result["historical_bias"]
        == "INSUFFICIENT_DATA"
    )

    assert result["similar_trades"] == 2
    assert result["sufficient_sample"] is False


def test_only_similar_trades_are_used():

    engine = HistoricalContextEngine(
        minimum_sample_size=2
    )

    trades = [
        make_trade(pnl=100),
        make_trade(pnl=200),
        make_trade(
            pnl=-1000,
            strategy="PULLBACK",
        ),
        make_trade(
            pnl=-1000,
            direction="BEARISH",
        ),
    ]

    result = engine.evaluate(
        trades,
        current_snapshot(),
    )

    assert result["similar_trades"] == 2

    assert (
        result["historical_bias"]
        == "SUPPORTIVE"
    )

    assert result["total_pnl"] == 300.0


def test_open_trades_are_not_used():

    engine = HistoricalContextEngine(
        minimum_sample_size=2
    )

    trades = [
        make_trade(pnl=100),
        make_trade(pnl=100),
        make_trade(
            pnl=-1000,
            status="OPEN",
        ),
    ]

    result = engine.evaluate(
        trades,
        current_snapshot(),
    )

    assert result["similar_trades"] == 2
    assert result["total_pnl"] == 200.0


def test_historical_context_is_advisory_only():

    engine = HistoricalContextEngine(
        minimum_sample_size=1
    )

    result = engine.evaluate(
        [
            make_trade(
                pnl=-100
            )
        ],
        current_snapshot(),
    )

    assert result["advisory_only"] is True

    assert (
        result[
            "can_override_live_safety"
        ]
        is False
    )


def test_matching_fields_are_returned():

    engine = HistoricalContextEngine(
        minimum_sample_size=1
    )

    snapshot = current_snapshot()

    result = engine.evaluate(
        [
            make_trade(
                pnl=100
            )
        ],
        snapshot,
    )

    assert (
        result["matching_fields"]
        == snapshot
    )


def test_invalid_snapshot_rejected():

    engine = HistoricalContextEngine()

    with pytest.raises(
        ValueError,
        match=(
            "decision_snapshot must be "
            "a dictionary"
        ),
    ):
        engine.evaluate(
            [],
            None,
        )


def test_invalid_minimum_sample_size_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "minimum_sample_size must be "
            "a positive integer"
        ),
    ):
        HistoricalContextEngine(
            minimum_sample_size=0
        )


def test_invalid_thresholds_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "Historical win-rate "
            "thresholds are invalid"
        ),
    ):
        HistoricalContextEngine(
            supportive_win_rate=30,
            negative_win_rate=60,
        )