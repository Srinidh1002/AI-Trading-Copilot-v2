from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)
from services.completed_candle_service import (
    CompletedCandleService,
)

from services.market_session_guard import (
    INDIA_TIMEZONE,
)

from services.market_holiday_calendar import (
    MarketHolidayCalendar,
)


def india_datetime(
    year,
    month,
    day,
    hour,
    minute,
):
    """
    Return an India-timezone-aware datetime
    for deterministic market-session tests.
    """

    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        tzinfo=INDIA_TIMEZONE,
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


def bullish_waiting_analysis():
    """
    Return a reusable bullish waiting setup.
    """

    return {
        "strategy": {
            "decision": "NO_TRADE",
            "direction": "BULLISH",
            "confidence": 90,
            "risk_flags": [],
            "strategy": "NO_TRADE",
        },
        "technical": {
            "indicators": {
                "atr": 16.0,
            },
        },
        "candlestick": {
            "support": 24150,
            "resistance": 24300,
        },
        "chart": {
            "patterns": [
                "DOUBLE_BOTTOM",
                "CONSOLIDATION",
            ],
        },
    }


# =================================================
# EXISTING CORE PIPELINE TESTS
# =================================================


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


def test_waiting_breakout_stays_waiting_when_candle_not_confirmed():

    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = (
        bullish_waiting_analysis()
    )

    option_builder = MagicMock()

    candle_service = MagicMock()

    candle_service.get_latest_completed_candle.return_value = {
        "timestamp": "2026-07-10T10:05:00+05:30",
        "open": 24280,
        "high": 24305,
        "low": 24270,
        "close": 24295,
        "volume": 10000,
    }

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
        completed_candle_service=candle_service,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24290,
    )

    assert (
        result["decision"]
        == "WAITING_FOR_BREAKOUT"
    )

    assert (
        result[
            "breakout_confirmation"
        ]["confirmed"]
        is False
    )

    assert (
        result["contract"]["selected"]
        is False
    )

    option_builder.build_chain.assert_not_called()


def test_completed_candle_confirms_breakout_and_selects_contract():

    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = (
        bullish_waiting_analysis()
    )

    option_builder = MagicMock()

    option_builder.build_chain.return_value = {
        "underlying": "NIFTY",
        "spot_price": 24320,
        "expiry": "14JUL2026",
        "contracts": valid_contracts(),
    }

    candle_service = MagicMock()

    candle_service.get_latest_completed_candle.return_value = {
        "timestamp": "2026-07-10T10:05:00+05:30",
        "open": 24290,
        "high": 24330,
        "low": 24280,
        "close": 24320,
        "volume": 20000,
    }

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
        completed_candle_service=candle_service,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24320,
    )

    assert (
        result[
            "breakout_confirmation"
        ]["confirmed"]
        is True
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
        result["contract"]["option_type"]
        == "CE"
    )

    option_builder.build_chain.assert_called_once()


# =================================================
# MARKET SESSION INTEGRATION TESTS
# =================================================


def test_market_closed_blocks_pipeline_before_analysis():

    analysis_pipeline = MagicMock()

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
        enforce_market_session=True,
        session_now=india_datetime(
            2026,
            7,
            11,
            10,
            30,
        ),
    )

    assert (
        result["decision"]
        == "MARKET_CLOSED"
    )

    assert (
        result["session_status"]["allowed"]
        is False
    )

    assert (
        result["session_status"]["market_open"]
        is False
    )

    analysis_pipeline.analyse.assert_not_called()

    option_builder.build_chain.assert_not_called()


def test_nse_holiday_blocks_pipeline_before_analysis():

    analysis_pipeline = MagicMock()

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
        enforce_market_session=True,
        session_now=india_datetime(
            2026,
            1,
            26,
            10,
            30,
        ),
    )

    assert (
        result["decision"]
        == "MARKET_HOLIDAY"
    )

    assert (
        result[
            "session_status"
        ]["is_market_holiday"]
        is True
    )

    assert (
        result["session_status"]["allowed"]
        is False
    )

    analysis_pipeline.analyse.assert_not_called()

    option_builder.build_chain.assert_not_called()


def test_custom_holiday_calendar_blocks_pipeline():

    analysis_pipeline = MagicMock()

    option_builder = MagicMock()

    custom_calendar = MarketHolidayCalendar(
        holidays=[
            "2026-07-10",
        ]
    )

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
        holiday_calendar=custom_calendar,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206.9,
        enforce_market_session=True,
        session_now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        ),
    )

    assert (
        result["decision"]
        == "MARKET_HOLIDAY"
    )

    assert (
        result[
            "session_status"
        ]["is_market_holiday"]
        is True
    )

    analysis_pipeline.analyse.assert_not_called()

    option_builder.build_chain.assert_not_called()


def test_valid_market_session_allows_pipeline_to_continue():

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
        enforce_market_session=True,
        session_now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        ),
    )

    assert (
        result["decision"]
        == "TRADE_READY"
    )

    assert (
        result["session_status"]["allowed"]
        is True
    )

    assert (
        result["session_status"]["status"]
        == "SESSION_VALID"
    )

    analysis_pipeline.analyse.assert_called_once()

    option_builder.build_chain.assert_called_once()


def test_completed_analysis_candle_populates_session_reporting():

    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = {
        "strategy": {
            "decision": "NO_TRADE",
            "direction": "NEUTRAL",
        },
        "timeframes": {
            "5m": pd.DataFrame({
                "timestamp": pd.to_datetime([
                    "2026-07-10 10:20:00+05:30",
                    "2026-07-10 10:25:00+05:30",
                ]),
                "Open": [24200, 24205],
                "High": [24210, 24215],
                "Low": [24195, 24200],
                "Close": [24205, 24210],
                "Volume": [100, 120],
            }),
        },
    }

    option_builder = MagicMock()
    candle_service = CompletedCandleService(
        market_client=MagicMock()
    )

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
        completed_candle_service=candle_service,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24206.9,
        enforce_market_session=True,
        session_now=india_datetime(2026, 7, 10, 10, 30),
    )

    assert result["completed_candle"]["timestamp"] == pd.Timestamp(
        "2026-07-10 10:25:00+05:30"
    )
    assert result["session_status"]["candle_timestamp"] is not None
    assert result["session_status"]["candle_age_minutes"] == 5.0
    assert result["session_status"]["candle_fresh"] is True
    candle_service.market_client.get_historical_data.assert_not_called()


def test_stale_completed_candle_blocks_option_chain():

    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = (
        bullish_waiting_analysis()
    )

    option_builder = MagicMock()

    candle_service = MagicMock()

    candle_service.get_latest_completed_candle.return_value = {
        "timestamp": "2026-07-10T10:05:00+05:30",
        "open": 24290,
        "high": 24330,
        "low": 24280,
        "close": 24320,
        "volume": 20000,
    }

    pipeline = LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=option_builder,
        completed_candle_service=candle_service,
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
        underlying="NIFTY",
        spot_price=24320,
        enforce_market_session=True,
        session_now=india_datetime(
            2026,
            7,
            10,
            10,
            30,
        ),
        maximum_candle_age_minutes=10,
    )

    assert (
        result["decision"]
        == "STALE_MARKET_DATA"
    )

    assert (
        result["session_status"]["allowed"]
        is False
    )

    assert (
        result[
            "session_status"
        ]["candle_fresh"]
        is False
    )

    assert (
        result["contract"]["selected"]
        is False
    )

    option_builder.build_chain.assert_not_called()


def test_default_pipeline_shares_injected_market_client():
    market_client = MagicMock()

    pipeline = LiveOptionDecisionPipeline(
        market_client=market_client,
    )

    assert pipeline.analysis_pipeline.data_service.client is market_client
    assert pipeline.option_chain_builder.market_client is market_client
    assert pipeline.completed_candle_service.market_client is market_client
