"""
Exception-safety tests for the live option decision pipeline.

Verifies that failures in:
- Market analysis
- Completed-candle retrieval
- Option-chain construction
- Contract selection
- Trade-plan construction

never produce accidental trade authorization.

Read-only.
No orders are placed.
"""

from unittest.mock import (
    MagicMock,
    patch,
)

import pytest

from services.market_data_validator import (
    MarketDataValidationError,
)

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)


def make_market_result(
    decision="TRADE",
    direction="BULLISH",
    atr=100,
):
    return {
        "strategy": {
            "decision": decision,
            "direction": direction,
        },
        "technical": {
            "indicators": {
                "atr": atr,
            },
        },
        "candlestick": {
            "support": 24100,
            "resistance": 24300,
        },
        "chart": {},
    }


def make_valid_contract():
    return {
        "symbol": "NIFTY14JUL2624200CE",
        "strike": 24200,
        "option_type": "CE",
        "expiry": "14JUL2026",
        "premium": 150.0,
        "bid": 149.5,
        "ask": 150.5,
        "volume": 20000,
        "open_interest": 30000,
        "delta": None,
        "lot_size": 75,
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


def test_market_analysis_exception_propagates_safely():

    (
        pipeline,
        analysis_pipeline,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline()

    analysis_pipeline.analyse.side_effect = (
        RuntimeError(
            "Market analysis failed."
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Market analysis failed",
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
        )

    option_chain_builder.build_chain.assert_not_called()

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )


def test_option_chain_exception_does_not_return_trade():

    (
        pipeline,
        _,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline()

    option_chain_builder.build_chain.side_effect = (
        RuntimeError(
            "Option chain unavailable."
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Option chain unavailable",
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
            capital=10000,
        )

    (
        completed_candle_service
        .get_latest_completed_candle
        .assert_not_called()
    )


def test_empty_option_chain_fails_closed():

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline()

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


def test_missing_contracts_key_fails_closed():

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline()

    option_chain_builder.build_chain.return_value = {
        "underlying": "NIFTY",
        "contracts_received": 0,
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


@patch(
    "services.live_option_decision_pipeline."
    "select_option_contract"
)
def test_contract_selector_exception_does_not_authorize_trade(
    mock_selector,
):

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline()

    option_chain_builder.build_chain.return_value = {
        "contracts": [
            make_valid_contract()
        ],
    }

    mock_selector.side_effect = (
        RuntimeError(
            "Contract selection failed."
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Contract selection failed",
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
            capital=10000,
        )


@patch(
    "services.live_option_decision_pipeline."
    "build_trade_plan"
)
def test_trade_plan_exception_does_not_authorize_trade(
    mock_trade_plan,
):

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline()

    option_chain_builder.build_chain.return_value = {
        "contracts": [
            make_valid_contract()
        ],
    }

    mock_trade_plan.side_effect = (
        RuntimeError(
            "Risk planning failed."
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Risk planning failed",
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
            capital=10000,
        )

    mock_trade_plan.assert_called_once()


def test_completed_candle_exception_stops_before_option_chain():

    market_result = make_market_result(
        decision="NO_TRADE",
        direction="BULLISH",
    )

    market_result["chart"] = {
        "breakout": True,
    }

    market_result["candlestick"] = {
        "support": 24100,
        "resistance": 24300,
    }

    (
        pipeline,
        _,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline(
        market_result=market_result
    )

    completed_candle_service\
        .get_latest_completed_candle\
        .side_effect = RuntimeError(
            "Historical candle service failed."
        )

    with patch(
        "services.live_option_decision_pipeline."
        "evaluate_setup_trigger"
    ) as mock_trigger:

        mock_trigger.return_value = {
            "status": "WAITING_FOR_BREAKOUT",
            "direction": "BULLISH",
            "trigger_type": "BREAKOUT",
            "trigger_price": 24300,
            "current_price": 24206,
            "support": 24100,
            "resistance": 24300,
            "reasons": [],
        }

        with pytest.raises(
            RuntimeError,
            match=(
                "Historical candle "
                "service failed"
            ),
        ):
            pipeline.analyse(
                exchange="NSE",
                symboltoken="99926000",
                underlying="NIFTY",
                spot_price=24206,
            )

    option_chain_builder.build_chain.assert_not_called()


def test_invalid_completed_candle_stops_before_option_chain():

    market_result = make_market_result(
        decision="NO_TRADE",
        direction="BULLISH",
    )

    (
        pipeline,
        _,
        option_chain_builder,
        completed_candle_service,
    ) = make_pipeline(
        market_result=market_result
    )

    completed_candle_service\
        .get_latest_completed_candle\
        .return_value = {
            "timestamp": (
                "2026-07-13T10:00:00+05:30"
            ),
            "open": 24200,
            "high": 24350,
            "low": 24150,

            # Deliberately missing close.
            "volume": 10000,
        }

    with patch(
        "services.live_option_decision_pipeline."
        "evaluate_setup_trigger"
    ) as mock_trigger:

        mock_trigger.return_value = {
            "status": "WAITING_FOR_BREAKOUT",
            "direction": "BULLISH",
            "trigger_type": "BREAKOUT",
            "trigger_price": 24300,
            "current_price": 24206,
            "support": 24100,
            "resistance": 24300,
            "reasons": [],
        }

        with pytest.raises(
            MarketDataValidationError,
            match="Close must be numeric",
        ):
            pipeline.analyse(
                exchange="NSE",
                symboltoken="99926000",
                underlying="NIFTY",
                spot_price=24206,
            )

    option_chain_builder.build_chain.assert_not_called()


@patch(
    "services.live_option_decision_pipeline."
    "build_trade_plan"
)
def test_rejected_trade_plan_remains_rejected(
    mock_trade_plan,
):

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline()

    option_chain_builder.build_chain.return_value = {
        "contracts": [
            make_valid_contract()
        ],
    }

    mock_trade_plan.return_value = {
        "allowed": False,
        "decision": "TRADE_REJECTED",
        "reasons": [
            "Risk limits exceeded."
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
        result["trade_plan"]["allowed"]
        is False
    )


@patch(
    "services.live_option_decision_pipeline."
    "build_trade_plan"
)
def test_missing_allowed_flag_fails_closed(
    mock_trade_plan,
):

    (
        pipeline,
        _,
        option_chain_builder,
        _,
    ) = make_pipeline()

    option_chain_builder.build_chain.return_value = {
        "contracts": [
            make_valid_contract()
        ],
    }

    mock_trade_plan.return_value = {
        "decision": "TRADE_ALLOWED",

        # Deliberately missing:
        # "allowed": True
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
        result["trade_plan"].get(
            "allowed",
            False,
        )
        is False
    )