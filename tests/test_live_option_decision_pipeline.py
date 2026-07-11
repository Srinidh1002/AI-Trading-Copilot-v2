from unittest.mock import MagicMock

import pytest

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)


def valid_contracts():
    return [
        {
            "symbol": "NIFTY14JUL2624200CE",
            "strike": 24200,
            "option_type": "CE",
            "expiry": "14JUL2026",
            "premium": 101.15,
            "bid": 103.55,
            "ask": 104.25,
            "volume": 491873590,
            "open_interest": 9405435,
            "delta": None,
        },
        {
            "symbol": "NIFTY14JUL2624200PE",
            "strike": 24200,
            "option_type": "PE",
            "expiry": "14JUL2026",
            "premium": 96.25,
            "bid": 87.65,
            "ask": 88.05,
            "volume": 414676535,
            "open_interest": 10295285,
            "delta": None,
        },
    ]


def test_no_trade_stops_before_option_chain():

    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = {
        "strategy": {
            "decision": "NO_TRADE",
            "direction": "BULLISH",
        }
    }

    option_builder = MagicMock()

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206.9,
    )

    assert result["decision"] == "NO_TRADE"

    assert (
        result["contract"]["selected"]
        is False
    )

    option_builder.build_chain.assert_not_called()


def test_bullish_trade_selects_ce():

    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = {
        "strategy": {
            "decision": "TRADE",
            "direction": "BULLISH",
        }
    }

    option_builder = MagicMock()

    option_builder.build_chain.return_value = {
        "underlying": "NIFTY",
        "spot_price": 24206.9,
        "expiry": "14JUL2026",
        "contracts": valid_contracts(),
    }

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206.9,
    )

    assert result["decision"] == "TRADE_READY"

    assert (
        result["contract"]["selected"]
        is True
    )

    assert (
        result["contract"]["option_type"]
        == "CE"
    )


def test_bearish_trade_selects_pe():

    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = {
        "strategy": {
            "decision": "TRADE",
            "direction": "BEARISH",
        }
    }

    option_builder = MagicMock()

    option_builder.build_chain.return_value = {
        "underlying": "NIFTY",
        "spot_price": 24206.9,
        "expiry": "14JUL2026",
        "contracts": valid_contracts(),
    }

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206.9,
    )

    assert result["decision"] == "TRADE_READY"

    assert (
        result["contract"]["option_type"]
        == "PE"
    )


def test_invalid_spot_price():

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=MagicMock(),
        option_chain_builder=MagicMock(),
    )

    with pytest.raises(
        ValueError,
        match="Spot price must be greater than zero",
    ):
        pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=0,
        )