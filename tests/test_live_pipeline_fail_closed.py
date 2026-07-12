"""
Fail-closed safety tests for the live option decision pipeline.

These tests verify that downstream option-chain and
trade-planning stages are not reached when an earlier
safety gate blocks the pipeline.

Read-only.
No orders are placed.
"""

from unittest.mock import MagicMock

import pytest

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)


def make_market_result(
    decision="NO_TRADE",
    direction="NEUTRAL",
):
    return {
        "strategy": {
            "decision": decision,
            "direction": direction,
        },
        "technical": {
            "indicators": {
                "atr": 100,
            },
        },
        "candlestick": {
            "support": 24100,
            "resistance": 24300,
        },
        "chart": {},
    }


def make_pipeline(
    market_result=None,
):
    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = (
        market_result
        if market_result is not None
        else make_market_result()
    )

    option_chain_builder = MagicMock()

    completed_candle_service = MagicMock()

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_chain_builder,
        completed_candle_service=(
            completed_candle_service
        ),
        holiday_calendar=set(),
    )

    return (
        pipeline,
        analysis_pipeline,
        option_chain_builder,
        completed_candle_service,
    )


def test_invalid_spot_price_stops_everything():

    (
        pipeline,
        analysis_pipeline,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline()

    with pytest.raises(
        ValueError,
        match=(
            "Spot price must be "
            "greater than zero"
        ),
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=0,
        )

    analysis_pipeline.analyse.assert_not_called()

    option_chain_builder.build_chain.assert_not_called()

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )


def test_invalid_capital_stops_everything():

    (
        pipeline,
        analysis_pipeline,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline()

    with pytest.raises(
        ValueError,
        match=(
            "Capital must be "
            "greater than zero"
        ),
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
            capital=0,
        )

    analysis_pipeline.analyse.assert_not_called()

    option_chain_builder.build_chain.assert_not_called()

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )


def test_invalid_candle_age_stops_everything():

    (
        pipeline,
        analysis_pipeline,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline()

    with pytest.raises(
        ValueError,
        match="maximum_candle_age_minutes",
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
            maximum_candle_age_minutes=0,
        )

    analysis_pipeline.analyse.assert_not_called()

    option_chain_builder.build_chain.assert_not_called()

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )


def test_no_trade_without_setup_stops_before_candle():

    (
        pipeline,
        analysis_pipeline,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline(
        market_result=make_market_result(
            decision="NO_TRADE",
            direction="NEUTRAL",
        )
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
    )

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    analysis_pipeline.analyse.assert_called_once()

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )

    option_chain_builder.build_chain.assert_not_called()

    assert (
        result["option_chain"]
        is None
    )

    assert (
        result["trade_plan"]
        is None
    )


def test_neutral_direction_never_builds_option_chain():

    (
        pipeline,
        _,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline(
        market_result=make_market_result(
            decision="TRADE",
            direction="NEUTRAL",
        )
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
    )

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    option_chain_builder.build_chain.assert_not_called()

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )

    assert (
        result["trade_plan"]
        is None
    )


def test_direct_trade_does_not_fetch_confirmation_candle():

    (
        pipeline,
        _,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline(
        market_result=make_market_result(
            decision="TRADE",
            direction="BULLISH",
        )
    )

    option_chain_builder.build_chain.return_value = {
        "contracts": [],
    }

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
    )

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )

    option_chain_builder.build_chain.assert_called_once()

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    assert (
        result["trade_plan"]
        is None
    )


def test_no_contract_stops_before_trade_plan():

    (
        pipeline,
        _,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline(
        market_result=make_market_result(
            decision="TRADE",
            direction="BULLISH",
        )
    )

    option_chain_builder.build_chain.return_value = {
        "contracts": [],
    }

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
        capital=10000,
    )

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    assert (
        result["contract"]["selected"]
        is False
    )

    assert (
        result["trade_plan"]
        is None
    )

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )


def test_missing_atr_rejects_before_trade_plan():

    market_result = make_market_result(
        decision="TRADE",
        direction="BULLISH",
    )

    market_result[
        "technical"
    ][
        "indicators"
    ][
        "atr"
    ] = 0

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline(
        market_result=market_result
    )

    option_chain_builder.build_chain.return_value = {
        "contracts": [
            {
                "symbol": (
                    "NIFTY14JUL2624200CE"
                ),
                "strike": 24200,
                "option_type": "CE",
                "expiry": "14JUL2026",
                "premium": 150,
                "bid": 149.5,
                "ask": 150.5,
                "volume": 20000,
                "open_interest": 30000,
                "delta": None,
                "lot_size": 75,
            }
        ],
    }

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
        capital=10000,
    )

    assert (
        result["decision"]
        == "TRADE_REJECTED"
    )

    assert (
        result["trade_plan"]
        is None
    )

    assert any(
        "ATR"
        in reason
        for reason in result[
            "reasons"
        ]
    )


def test_contract_selection_without_capital_returns_trade_ready():

    (
        pipeline,
        _,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline(
        market_result=make_market_result(
            decision="TRADE",
            direction="BULLISH",
        )
    )

    option_chain_builder.build_chain.return_value = {
        "contracts": [
            {
                "symbol": (
                    "NIFTY14JUL2624200CE"
                ),
                "strike": 24200,
                "option_type": "CE",
                "expiry": "14JUL2026",
                "premium": 150,
                "bid": 149.5,
                "ask": 150.5,
                "volume": 20000,
                "open_interest": 30000,
                "delta": None,
                "lot_size": 75,
            }
        ],
    }

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
        capital=None,
    )

    assert (
        result["decision"]
        == "TRADE_READY"
    )

    assert (
        result["contract"]["selected"]
        is True
    )

    assert (
        result["trade_plan"]
        is None
    )

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )


def test_pipeline_remains_read_only():

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline(
        market_result=make_market_result(
            decision="TRADE",
            direction="BULLISH",
        )
    )

    option_chain_builder.build_chain.return_value = {
        "contracts": [],
    }

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206,
    )

    assert (
        result["decision"]
        in {
            "NO_TRADE",
            "TRADE_READY",
            "TRADE_ALLOWED",
            "TRADE_REJECTED",
        }
    )

    assert not hasattr(
        pipeline,
        "place_order",
    )