import pytest

from services.strategy_regime_performance import (
    StrategyRegimePerformanceEngine,
)


def make_trade(
    *,
    status="CLOSED",
    realized_pnl=100.0,
    strategy="TREND_CONTINUATION",
    market_regime="TRENDING_BEARISH",
    trade_id=None,
    closed_at=None,
):
    return {
        "trade_id": trade_id,
        "status": status,
        "realized_pnl": realized_pnl,
        "closed_at": closed_at,
        "decision_snapshot": {
            "strategy": strategy,
            "market_regime": market_regime,
        },
    }


def make_engine(
    minimum_sample_size=2,
):
    return (
        StrategyRegimePerformanceEngine(
            minimum_sample_size=(
                minimum_sample_size
            )
        )
    )


def test_none_trades_rejected():
    with pytest.raises(
        ValueError,
        match="trades must not be None",
    ):
        make_engine().analyze(
            None
        )


def test_invalid_trades_rejected():
    with pytest.raises(
        ValueError,
        match="trades must be a list or tuple",
    ):
        make_engine().analyze(
            {
                "status": "CLOSED",
            }
        )


def test_invalid_minimum_sample_size_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "minimum_sample_size must be "
            "a positive integer"
        ),
    ):
        StrategyRegimePerformanceEngine(
            minimum_sample_size=0
        )


def test_boolean_minimum_sample_size_rejected():
    with pytest.raises(
        ValueError
    ):
        StrategyRegimePerformanceEngine(
            minimum_sample_size=True
        )


def test_non_dictionary_trades_ignored():
    result = make_engine().analyze(
        [
            None,
            "bad",
            123,
            make_trade(),
        ]
    )

    assert result["trades_observed"] == 1


def test_open_trades_not_analyzed():
    result = make_engine().analyze(
        [
            make_trade(
                status="OPEN"
            ),
        ]
    )

    assert (
        result["closed_trades_analyzed"]
        == 0
    )


def test_closed_trade_analyzed():
    result = make_engine().analyze(
        [
            make_trade(),
        ]
    )

    assert (
        result["closed_trades_analyzed"]
        == 1
    )


def test_invalid_realized_pnl_ignored():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl="bad"
            ),
        ]
    )

    assert (
        result["closed_trades_analyzed"]
        == 0
    )


def test_strategy_regime_combination_created():
    result = make_engine().analyze(
        [
            make_trade(),
        ]
    )

    combination = result[
        "combinations"
    ][0]

    assert (
        combination["strategy"]
        == "TREND_CONTINUATION"
    )

    assert (
        combination["market_regime"]
        == "TRENDING_BEARISH"
    )


def test_same_combination_grouped():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=-50
            ),
        ]
    )

    assert (
        result["combinations_observed"]
        == 1
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "trades"
        ]
        == 2
    )


def test_different_regimes_separated():
    result = make_engine().analyze(
        [
            make_trade(
                market_regime=(
                    "TRENDING_BEARISH"
                )
            ),
            make_trade(
                market_regime="RANGE_BOUND"
            ),
        ]
    )

    assert (
        result["combinations_observed"]
        == 2
    )


def test_different_strategies_separated():
    result = make_engine().analyze(
        [
            make_trade(
                strategy="A"
            ),
            make_trade(
                strategy="B"
            ),
        ]
    )

    assert (
        result["combinations_observed"]
        == 2
    )


def test_win_loss_breakeven_metrics():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=-50
            ),
            make_trade(
                realized_pnl=0
            ),
        ]
    )

    metrics = result[
        "combinations"
    ][0][
        "metrics"
    ]

    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["breakeven"] == 1


def test_win_rate_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=50
            ),
            make_trade(
                realized_pnl=-20
            ),
            make_trade(
                realized_pnl=-30
            ),
        ]
    )

    metrics = result[
        "combinations"
    ][0][
        "metrics"
    ]

    assert metrics["win_rate"] == 50.0


def test_total_pnl_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=-40
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "total_pnl"
        ]
        == 60.0
    )


def test_average_pnl_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=-40
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "average_pnl"
        ]
        == 30.0
    )


def test_average_win_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=50
            ),
            make_trade(
                realized_pnl=-20
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "average_win"
        ]
        == 75.0
    )


def test_average_loss_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=-20
            ),
            make_trade(
                realized_pnl=-40
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "average_loss"
        ]
        == -30.0
    )


def test_profit_factor_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=50
            ),
            make_trade(
                realized_pnl=-50
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "profit_factor"
        ]
        == 3.0
    )


def test_profit_factor_none_without_losses():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=50
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "profit_factor"
        ]
        is None
    )


def test_longest_win_streak_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=10
            ),
            make_trade(
                realized_pnl=20
            ),
            make_trade(
                realized_pnl=30
            ),
            make_trade(
                realized_pnl=-10
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "longest_win_streak"
        ]
        == 3
    )


def test_longest_loss_streak_calculated():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=-10
            ),
            make_trade(
                realized_pnl=-20
            ),
            make_trade(
                realized_pnl=30
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "longest_loss_streak"
        ]
        == 2
    )


def test_breakeven_resets_streak():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=10
            ),
            make_trade(
                realized_pnl=0
            ),
            make_trade(
                realized_pnl=20
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "metrics"
        ][
            "longest_win_streak"
        ]
        == 1
    )


def test_insufficient_sample_observation():
    result = make_engine(
        minimum_sample_size=3
    ).analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=100
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "research_observation"
        ]
        == "INSUFFICIENT_SAMPLE"
    )


def test_historically_positive_observation():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=100
            ),
            make_trade(
                realized_pnl=50
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "research_observation"
        ]
        == "HISTORICALLY_POSITIVE"
    )


def test_historically_negative_observation():
    result = make_engine().analyze(
        [
            make_trade(
                realized_pnl=-100
            ),
            make_trade(
                realized_pnl=-50
            ),
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "research_observation"
        ]
        == "HISTORICALLY_NEGATIVE"
    )


def test_positive_combinations_collected():
    result = make_engine().analyze(
        [
            make_trade(
                strategy="A",
                realized_pnl=100,
            ),
            make_trade(
                strategy="A",
                realized_pnl=50,
            ),
        ]
    )

    assert (
        len(
            result[
                "positive_combinations"
            ]
        )
        == 1
    )


def test_negative_combinations_collected():
    result = make_engine().analyze(
        [
            make_trade(
                strategy="A",
                realized_pnl=-100,
            ),
            make_trade(
                strategy="A",
                realized_pnl=-50,
            ),
        ]
    )

    assert (
        len(
            result[
                "negative_combinations"
            ]
        )
        == 1
    )


def test_best_observed_combination_selected():
    result = make_engine().analyze(
        [
            make_trade(
                strategy="A",
                realized_pnl=100,
            ),
            make_trade(
                strategy="A",
                realized_pnl=100,
            ),
            make_trade(
                strategy="B",
                realized_pnl=10,
            ),
            make_trade(
                strategy="B",
                realized_pnl=10,
            ),
        ]
    )

    assert (
        result[
            "best_observed_combination"
        ][
            "strategy"
        ]
        == "A"
    )


def test_worst_observed_combination_selected():
    result = make_engine().analyze(
        [
            make_trade(
                strategy="A",
                realized_pnl=100,
            ),
            make_trade(
                strategy="A",
                realized_pnl=100,
            ),
            make_trade(
                strategy="B",
                realized_pnl=-100,
            ),
            make_trade(
                strategy="B",
                realized_pnl=-100,
            ),
        ]
    )

    assert (
        result[
            "worst_observed_combination"
        ][
            "strategy"
        ]
        == "B"
    )


def test_no_best_combination_without_sufficient_sample():
    result = make_engine(
        minimum_sample_size=5
    ).analyze(
        [
            make_trade(),
        ]
    )

    assert (
        result[
            "best_observed_combination"
        ]
        is None
    )


def test_source_decision_supported():
    trade = {
        "status": "CLOSED",
        "realized_pnl": 100,
        "source_decision": {
            "strategy": "BREAKOUT",
            "market_regime": "VOLATILE",
        },
    }

    result = make_engine().analyze(
        [
            trade,
        ]
    )

    combination = result[
        "combinations"
    ][0]

    assert (
        combination["strategy"]
        == "BREAKOUT"
    )

    assert (
        combination["market_regime"]
        == "VOLATILE"
    )


def test_top_level_strategy_regime_supported():
    trade = {
        "status": "CLOSED",
        "realized_pnl": 100,
        "strategy": "A",
        "market_regime": "B",
    }

    result = make_engine().analyze(
        [
            trade,
        ]
    )

    combination = result[
        "combinations"
    ][0]

    assert combination["strategy"] == "A"
    assert combination["market_regime"] == "B"


def test_nested_regime_dictionary_supported():
    trade = make_trade()

    trade[
        "decision_snapshot"
    ][
        "market_regime"
    ] = {
        "primary_regime": (
            "TRENDING_BEARISH"
        )
    }

    result = make_engine().analyze(
        [
            trade,
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "market_regime"
        ]
        == "TRENDING_BEARISH"
    )


def test_missing_strategy_normalized_unknown():
    trade = make_trade()

    del trade[
        "decision_snapshot"
    ][
        "strategy"
    ]

    result = make_engine().analyze(
        [
            trade,
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "strategy"
        ]
        == "UNKNOWN"
    )


def test_missing_regime_normalized_unknown():
    trade = make_trade()

    del trade[
        "decision_snapshot"
    ][
        "market_regime"
    ]

    result = make_engine().analyze(
        [
            trade,
        ]
    )

    assert (
        result[
            "combinations"
        ][0][
            "market_regime"
        ]
        == "UNKNOWN"
    )


def test_trade_id_preserved():
    result = make_engine().analyze(
        [
            make_trade(
                trade_id="T1"
            ),
        ]
    )

    assert (
        result[
            "trade_records"
        ][0][
            "trade_id"
        ]
        == "T1"
    )


def test_closed_at_preserved_as_timestamp():
    result = make_engine().analyze(
        [
            make_trade(
                closed_at="T1"
            ),
        ]
    )

    assert (
        result[
            "trade_records"
        ][0][
            "timestamp"
        ]
        == "T1"
    )


def test_result_read_only():
    result = make_engine().analyze(
        []
    )

    assert result["read_only"] is True

    assert (
        result[
            "historical_research_only"
        ]
        is True
    )


def test_input_not_modified():
    trades = [
        make_trade(
            realized_pnl=100
        ),
    ]

    original = [
        make_trade(
            realized_pnl=100
        ),
    ]

    make_engine().analyze(
        trades
    )

    assert trades == original