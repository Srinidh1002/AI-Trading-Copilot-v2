"""
Tests for persistent audit logging integration
in the live option decision pipeline.

Persistence must remain optional and must never
change or authorize a trading decision.
"""

from unittest.mock import (
    MagicMock,
    patch,
)

from services.live_option_decision_pipeline import (
    LiveOptionDecisionPipeline,
)


def make_market_result():
    return {
        "strategy": {
            "decision": "NO_TRADE",
            "direction": "NEUTRAL",
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
    audit_logger=None,
    persist_audit=False,
):
    analysis_pipeline = MagicMock()

    analysis_pipeline.analyse.return_value = (
        make_market_result()
    )

    return LiveOptionDecisionPipeline(
        analysis_pipeline=analysis_pipeline,
        option_chain_builder=MagicMock(),
        completed_candle_service=MagicMock(),
        holiday_calendar=set(),
        audit_logger=audit_logger,
        persist_audit=persist_audit,
    )


def run_no_trade_analysis(
    pipeline,
):
    with patch(
        "services.live_option_decision_pipeline."
        "evaluate_setup_trigger"
    ) as mock_trigger:

        mock_trigger.return_value = {
            "status": "NO_SETUP",
            "direction": "NEUTRAL",
            "trigger_price": None,
            "reasons": [
                "No valid setup."
            ],
        }

        return pipeline.analyse(
            exchange="NSE",
            symboltoken="99926000",
            underlying="NIFTY",
            spot_price=24206,
        )


def test_persistence_disabled_by_default():

    logger = MagicMock()

    pipeline = make_pipeline(
        audit_logger=logger,
    )

    result = run_no_trade_analysis(
        pipeline
    )

    logger.log.assert_not_called()

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    assert result[
        "audit_persistence"
    ] == {
        "enabled": False,
        "persisted": False,
        "error": None,
    }


def test_enabled_persistence_logs_once():

    logger = MagicMock()

    pipeline = make_pipeline(
        audit_logger=logger,
        persist_audit=True,
    )

    result = run_no_trade_analysis(
        pipeline
    )

    logger.log.assert_called_once()

    assert (
        result["audit_persistence"][
            "enabled"
        ]
        is True
    )

    assert (
        result["audit_persistence"][
            "persisted"
        ]
        is True
    )

    assert (
        result["audit_persistence"][
            "error"
        ]
        is None
    )


def test_persistence_receives_audit_trail():

    logger = MagicMock()

    pipeline = make_pipeline(
        audit_logger=logger,
        persist_audit=True,
    )

    result = run_no_trade_analysis(
        pipeline
    )

    call_kwargs = (
        logger.log.call_args.kwargs
    )

    assert (
        call_kwargs["audit_trail"]
        == result["audit_trail"]
    )

    assert (
        call_kwargs[
            "audit_trail"
        ][
            "final_decision"
        ]
        == "NO_TRADE"
    )


def test_persistence_receives_metadata():

    logger = MagicMock()

    pipeline = make_pipeline(
        audit_logger=logger,
        persist_audit=True,
    )

    run_no_trade_analysis(
        pipeline
    )

    metadata = (
        logger.log
        .call_args
        .kwargs[
            "metadata"
        ]
    )

    assert (
        metadata["exchange"]
        == "NSE"
    )

    assert (
        metadata["symboltoken"]
        == "99926000"
    )

    assert (
        metadata["underlying"]
        == "NIFTY"
    )

    assert (
        metadata["spot_price"]
        == 24206
    )

    assert (
        metadata["final_decision"]
        == "NO_TRADE"
    )


def test_logging_failure_does_not_change_decision():

    logger = MagicMock()

    logger.log.side_effect = (
        OSError(
            "Disk unavailable."
        )
    )

    pipeline = make_pipeline(
        audit_logger=logger,
        persist_audit=True,
    )

    result = run_no_trade_analysis(
        pipeline
    )

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    assert (
        result["audit_trail"][
            "final_decision"
        ]
        == "NO_TRADE"
    )

    assert (
        result["audit_persistence"][
            "enabled"
        ]
        is True
    )

    assert (
        result["audit_persistence"][
            "persisted"
        ]
        is False
    )

    assert (
        result["audit_persistence"][
            "error"
        ]
        == "Disk unavailable."
    )


def test_logging_failure_does_not_raise():

    logger = MagicMock()

    logger.log.side_effect = (
        RuntimeError(
            "Audit logger failed."
        )
    )

    pipeline = make_pipeline(
        audit_logger=logger,
        persist_audit=True,
    )

    result = run_no_trade_analysis(
        pipeline
    )

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    assert (
        result["audit_persistence"][
            "persisted"
        ]
        is False
    )


def test_audit_trail_exists_when_persistence_disabled():

    pipeline = make_pipeline(
        persist_audit=False,
    )

    result = run_no_trade_analysis(
        pipeline
    )

    assert "audit_trail" in result

    assert (
        result["audit_trail"][
            "final_decision"
        ]
        == result["decision"]
    )


def test_persistence_cannot_upgrade_decision():

    logger = MagicMock()

    logger.log.return_value = {
        "final_decision": (
            "TRADE_ALLOWED"
        )
    }

    pipeline = make_pipeline(
        audit_logger=logger,
        persist_audit=True,
    )

    result = run_no_trade_analysis(
        pipeline
    )

    assert (
        result["decision"]
        == "NO_TRADE"
    )

    assert (
        result["audit_trail"][
            "final_decision"
        ]
        == "NO_TRADE"
    )