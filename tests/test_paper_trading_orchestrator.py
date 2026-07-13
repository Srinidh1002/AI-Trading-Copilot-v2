"""
Tests for PaperTradingOrchestrator.

Verifies:
- TRADE_ALLOWED opens paper trades
- non-trade decisions are skipped
- disabled orchestration is skipped
- duplicate source decisions are blocked
- failed opens are isolated
- failed opens can be retried
- metadata is preserved
- source references are forwarded
- inputs are not mutated
- validation fails closed
- helper methods behave correctly
- no broker execution behavior is introduced
"""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from services.paper_trading_orchestrator import (
    PaperTradingOrchestrator,
)


# ============================================================
# HELPERS
# ============================================================


class FakeTrade:
    """
    Minimal trade object for orchestrator tests.
    """

    def __init__(
        self,
        trade_id="paper-test-001",
    ):
        self.trade_id = trade_id

    def as_dict(
        self,
    ):
        return {
            "trade_id": self.trade_id,
            "status": "OPEN",
        }


def make_pipeline_result(
    decision="TRADE_ALLOWED",
):
    """
    Build a representative pipeline result.
    """

    return {
        "decision": decision,
        "direction": "BULLISH",
        "contract": {
            "selected": True,
            "symbol": "NIFTY_TEST_CE",
            "option_type": "CE",
            "strike": 24200.0,
            "premium": 100.0,
            "lot_size": 75,
            "expiry": "2026-07-30",
        },
        "trade_plan": {
            "allowed": True,
            "decision": decision,
            "levels": {
                "option_entry_price": 100.0,
                "option_stop_loss": 80.0,
                "option_target": 140.0,
            },
            "risk": {
                "allowed": True,
                "lots": 1,
                "quantity": 75,
                "required_capital": 7500.0,
                "estimated_maximum_loss": 1500.0,
            },
        },
    }


def make_orchestrator(
    enabled=True,
):
    """
    Build orchestrator with mocked paper engine.
    """

    engine = MagicMock()

    engine.open_trade.return_value = (
        FakeTrade()
    )

    orchestrator = (
        PaperTradingOrchestrator(
            paper_trading_engine=engine,
            enabled=enabled,
        )
    )

    return (
        orchestrator,
        engine,
    )


def process_allowed(
    orchestrator,
    source_decision_id=(
        "decision-001"
    ),
    **kwargs,
):
    """
    Process one valid allowed decision.
    """

    arguments = {
        "pipeline_result": (
            make_pipeline_result()
        ),
        "underlying": "NIFTY",
        "exchange": "NSE",
        "symboltoken": "99926000",
        "source_decision_id": (
            source_decision_id
        ),
        "source_audit_ref": (
            "audit-001"
        ),
        "opened_at": (
            "2026-07-12T09:15:00+00:00"
        ),
        "metadata": {
            "test": True,
        },
        "trade_id": (
            "paper-test-001"
        ),
    }

    arguments.update(
        kwargs
    )

    return (
        orchestrator.process_decision(
            **arguments
        )
    )


# ============================================================
# CONSTRUCTOR
# ============================================================


def test_requires_paper_trading_engine():

    with pytest.raises(
        ValueError,
        match=(
            "paper_trading_engine is required"
        ),
    ):
        PaperTradingOrchestrator(
            paper_trading_engine=None
        )


def test_enabled_must_be_boolean():

    engine = MagicMock()

    with pytest.raises(
        ValueError,
        match=(
            "enabled must be a boolean"
        ),
    ):
        PaperTradingOrchestrator(
            paper_trading_engine=engine,
            enabled="yes",
        )


def test_enabled_defaults_true():

    orchestrator, _ = (
        make_orchestrator()
    )

    assert (
        orchestrator.enabled
        is True
    )


# ============================================================
# TRADE ALLOWED
# ============================================================


def test_trade_allowed_opens_paper_trade():

    orchestrator, engine = (
        make_orchestrator()
    )

    result = process_allowed(
        orchestrator
    )

    engine.open_trade.assert_called_once()

    assert (
        result["status"]
        == "OPENED"
    )

    assert (
        result["opened"]
        is True
    )

    assert (
        result["skipped"]
        is False
    )

    assert (
        result["failed"]
        is False
    )


def test_opened_result_contains_trade_id():

    orchestrator, _ = (
        make_orchestrator()
    )

    result = process_allowed(
        orchestrator
    )

    assert (
        result["trade_id"]
        == "paper-test-001"
    )


def test_opened_result_contains_trade():

    orchestrator, _ = (
        make_orchestrator()
    )

    result = process_allowed(
        orchestrator
    )

    assert result["trade"] == {
        "trade_id": (
            "paper-test-001"
        ),
        "status": "OPEN",
    }


def test_opened_result_reason():

    orchestrator, _ = (
        make_orchestrator()
    )

    result = process_allowed(
        orchestrator
    )

    assert (
        result["reason"]
        == "PAPER_TRADE_OPENED"
    )


# ============================================================
# ARGUMENT FORWARDING
# ============================================================


def test_pipeline_result_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    pipeline_result = (
        make_pipeline_result()
    )

    orchestrator.process_decision(
        pipeline_result=(
            pipeline_result
        ),
        underlying="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs[
            "pipeline_result"
        ]
        == pipeline_result
    )


def test_underlying_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs["underlying"]
        == "NIFTY"
    )


def test_exchange_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs["exchange"]
        == "NSE"
    )


def test_symboltoken_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs["symboltoken"]
        == "99926000"
    )


def test_source_decision_id_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator,
        source_decision_id=(
            "decision-special"
        ),
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs[
            "source_decision_id"
        ]
        == "decision-special"
    )


def test_source_audit_ref_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs[
            "source_audit_ref"
        ]
        == "audit-001"
    )


def test_opened_at_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs["opened_at"]
        == (
            "2026-07-12T09:15:00+00:00"
        )
    )


def test_trade_id_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs["trade_id"]
        == "paper-test-001"
    )


# ============================================================
# METADATA
# ============================================================


def test_metadata_is_forwarded():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        engine.open_trade.call_args.kwargs
    )

    assert (
        call_kwargs["metadata"][
            "test"
        ]
        is True
    )


def test_orchestrator_metadata_is_added():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    metadata = (
        engine.open_trade
        .call_args
        .kwargs[
            "metadata"
        ]
    )

    assert (
        metadata[
            "orchestrated_by"
        ]
        == (
            "PaperTradingOrchestrator"
        )
    )

    assert (
        metadata[
            "paper_trade"
        ]
        is True
    )


def test_existing_metadata_values_not_overwritten():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator,
        metadata={
            "orchestrated_by": (
                "custom"
            ),
            "paper_trade": False,
        },
    )

    metadata = (
        engine.open_trade
        .call_args
        .kwargs[
            "metadata"
        ]
    )

    assert (
        metadata[
            "orchestrated_by"
        ]
        == "custom"
    )

    assert (
        metadata[
            "paper_trade"
        ]
        is False
    )


# ============================================================
# NON-TRADE DECISIONS
# ============================================================


@pytest.mark.parametrize(
    "decision",
    [
        "NO_TRADE",
        "TRADE_REJECTED",
        "WAITING_FOR_BREAKOUT",
        "MARKET_CLOSED",
        "BLOCKED",
    ],
)
def test_non_trade_decisions_are_skipped(
    decision,
):

    orchestrator, engine = (
        make_orchestrator()
    )

    result = (
        orchestrator.process_decision(
            pipeline_result=(
                make_pipeline_result(
                    decision=decision
                )
            ),
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
        )
    )

    engine.open_trade.assert_not_called()

    assert (
        result["status"]
        == "SKIPPED"
    )

    assert (
        result["reason"]
        == (
            "DECISION_NOT_TRADE_ALLOWED"
        )
    )

    assert (
        result["skipped"]
        is True
    )


# ============================================================
# DISABLED
# ============================================================


def test_disabled_orchestrator_skips():

    orchestrator, engine = (
        make_orchestrator(
            enabled=False
        )
    )

    result = process_allowed(
        orchestrator
    )

    engine.open_trade.assert_not_called()

    assert (
        result["status"]
        == "SKIPPED"
    )

    assert (
        result["reason"]
        == (
            "PAPER_TRADING_DISABLED"
        )
    )


# ============================================================
# DUPLICATE PROTECTION
# ============================================================


def test_duplicate_source_decision_is_skipped():

    orchestrator, engine = (
        make_orchestrator()
    )

    first = process_allowed(
        orchestrator,
        source_decision_id=(
            "duplicate-001"
        ),
    )

    second = process_allowed(
        orchestrator,
        source_decision_id=(
            "duplicate-001"
        ),
    )

    assert (
        first["status"]
        == "OPENED"
    )

    assert (
        second["status"]
        == "SKIPPED"
    )

    assert (
        second["reason"]
        == (
            "DUPLICATE_SOURCE_DECISION"
        )
    )

    assert (
        engine.open_trade.call_count
        == 1
    )


def test_different_decision_ids_can_open():

    orchestrator, engine = (
        make_orchestrator()
    )

    first = process_allowed(
        orchestrator,
        source_decision_id=(
            "decision-001"
        ),
    )

    second = process_allowed(
        orchestrator,
        source_decision_id=(
            "decision-002"
        ),
        trade_id="paper-test-002",
    )

    assert (
        first["status"]
        == "OPENED"
    )

    assert (
        second["status"]
        == "OPENED"
    )

    assert (
        engine.open_trade.call_count
        == 2
    )


def test_none_decision_id_does_not_use_duplicate_tracking():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator,
        source_decision_id=None,
        trade_id="trade-001",
    )

    process_allowed(
        orchestrator,
        source_decision_id=None,
        trade_id="trade-002",
    )

    assert (
        engine.open_trade.call_count
        == 2
    )


# ============================================================
# FAILURE ISOLATION
# ============================================================


def test_engine_failure_returns_failed_result():

    orchestrator, engine = (
        make_orchestrator()
    )

    engine.open_trade.side_effect = (
        RuntimeError(
            "Paper engine failed."
        )
    )

    result = process_allowed(
        orchestrator
    )

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["failed"]
        is True
    )

    assert (
        result["opened"]
        is False
    )

    assert (
        result["error"]
        == "Paper engine failed."
    )


def test_engine_failure_does_not_raise():

    orchestrator, engine = (
        make_orchestrator()
    )

    engine.open_trade.side_effect = (
        OSError(
            "Storage unavailable."
        )
    )

    result = process_allowed(
        orchestrator
    )

    assert (
        result["status"]
        == "FAILED"
    )


def test_failed_decision_is_not_marked_processed():

    orchestrator, engine = (
        make_orchestrator()
    )

    engine.open_trade.side_effect = (
        RuntimeError(
            "Temporary failure."
        )
    )

    process_allowed(
        orchestrator,
        source_decision_id=(
            "retry-001"
        ),
    )

    assert (
        orchestrator
        .has_processed_decision(
            "retry-001"
        )
        is False
    )


def test_failed_open_can_be_retried():

    orchestrator, engine = (
        make_orchestrator()
    )

    engine.open_trade.side_effect = [
        RuntimeError(
            "Temporary failure."
        ),
        FakeTrade(
            "retry-trade"
        ),
    ]

    first = process_allowed(
        orchestrator,
        source_decision_id=(
            "retry-decision"
        ),
    )

    second = process_allowed(
        orchestrator,
        source_decision_id=(
            "retry-decision"
        ),
    )

    assert (
        first["status"]
        == "FAILED"
    )

    assert (
        second["status"]
        == "OPENED"
    )

    assert (
        engine.open_trade.call_count
        == 2
    )


# ============================================================
# PROCESSED DECISION HELPERS
# ============================================================


def test_successful_decision_is_marked_processed():

    orchestrator, _ = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator,
        source_decision_id=(
            "processed-001"
        ),
    )

    assert (
        orchestrator
        .has_processed_decision(
            "processed-001"
        )
        is True
    )


def test_get_processed_decision_ids():

    orchestrator, _ = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator,
        source_decision_id="one",
    )

    process_allowed(
        orchestrator,
        source_decision_id="two",
        trade_id="trade-two",
    )

    assert (
        orchestrator
        .get_processed_decision_ids()
        == {
            "one",
            "two",
        }
    )


def test_processed_decision_ids_return_copy():

    orchestrator, _ = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator,
        source_decision_id="one",
    )

    result = (
        orchestrator
        .get_processed_decision_ids()
    )

    result.add(
        "external"
    )

    assert (
        orchestrator
        .has_processed_decision(
            "external"
        )
        is False
    )


def test_clear_processed_decision_ids():

    orchestrator, _ = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator,
        source_decision_id="one",
    )

    orchestrator.clear_processed_decision_ids()

    assert (
        orchestrator
        .get_processed_decision_ids()
        == set()
    )


# ============================================================
# INPUT IMMUTABILITY
# ============================================================


def test_pipeline_result_not_mutated():

    orchestrator, engine = (
        make_orchestrator()
    )

    pipeline_result = (
        make_pipeline_result()
    )

    original = deepcopy(
        pipeline_result
    )

    orchestrator.process_decision(
        pipeline_result=(
            pipeline_result
        ),
        underlying="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
    )

    assert (
        pipeline_result
        == original
    )


def test_metadata_not_mutated():

    orchestrator, _ = (
        make_orchestrator()
    )

    metadata = {
        "nested": {
            "value": 1,
        }
    }

    original = deepcopy(
        metadata
    )

    process_allowed(
        orchestrator,
        metadata=metadata,
    )

    assert (
        metadata
        == original
    )


def test_engine_cannot_mutate_original_pipeline_result():

    orchestrator, engine = (
        make_orchestrator()
    )

    pipeline_result = (
        make_pipeline_result()
    )

    original = deepcopy(
        pipeline_result
    )

    def mutate_input(
        **kwargs,
    ):
        kwargs[
            "pipeline_result"
        ][
            "decision"
        ] = "MUTATED"

        return FakeTrade()

    engine.open_trade.side_effect = (
        mutate_input
    )

    orchestrator.process_decision(
        pipeline_result=(
            pipeline_result
        ),
        underlying="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
    )

    assert (
        pipeline_result
        == original
    )


# ============================================================
# ALIAS
# ============================================================


def test_process_alias():

    orchestrator, engine = (
        make_orchestrator()
    )

    result = (
        orchestrator.process(
            make_pipeline_result(),
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
            source_decision_id=(
                "alias-001"
            ),
        )
    )

    assert (
        result["status"]
        == "OPENED"
    )

    engine.open_trade.assert_called_once()


# ============================================================
# VALIDATION
# ============================================================


@pytest.mark.parametrize(
    "pipeline_result",
    [
        None,
        [],
        "TRADE_ALLOWED",
        123,
    ],
)
def test_invalid_pipeline_result_type_rejected(
    pipeline_result,
):

    orchestrator, _ = (
        make_orchestrator()
    )

    with pytest.raises(
        ValueError,
        match=(
            "pipeline_result must be a dictionary"
        ),
    ):
        orchestrator.process_decision(
            pipeline_result=(
                pipeline_result
            ),
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
        )


def test_missing_decision_rejected():

    orchestrator, _ = (
        make_orchestrator()
    )

    with pytest.raises(
        ValueError,
        match=(
            "must contain decision"
        ),
    ):
        orchestrator.process_decision(
            pipeline_result={},
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
        )


@pytest.mark.parametrize(
    "decision",
    [
        None,
        123,
        [],
    ],
)
def test_non_string_decision_rejected(
    decision,
):

    orchestrator, _ = (
        make_orchestrator()
    )

    with pytest.raises(
        ValueError,
        match=(
            "decision must be a string"
        ),
    ):
        orchestrator.process_decision(
            pipeline_result={
                "decision": decision,
            },
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
        )


@pytest.mark.parametrize(
    "decision",
    [
        "",
        "   ",
    ],
)
def test_empty_decision_rejected(
    decision,
):

    orchestrator, _ = (
        make_orchestrator()
    )

    with pytest.raises(
        ValueError,
        match=(
            "decision must not be empty"
        ),
    ):
        orchestrator.process_decision(
            pipeline_result={
                "decision": decision,
            },
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        (
            "underlying",
            "",
        ),
        (
            "exchange",
            "",
        ),
        (
            "symboltoken",
            "",
        ),
    ],
)
def test_required_text_empty_rejected(
    field_name,
    value,
):

    orchestrator, _ = (
        make_orchestrator()
    )

    kwargs = {
        "pipeline_result": (
            make_pipeline_result()
        ),
        "underlying": "NIFTY",
        "exchange": "NSE",
        "symboltoken": "99926000",
    }

    kwargs[
        field_name
    ] = value

    with pytest.raises(
        ValueError,
        match=(
            f"{field_name} must not be empty"
        ),
    ):
        orchestrator.process_decision(
            **kwargs
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        (
            "underlying",
            123,
        ),
        (
            "exchange",
            [],
        ),
        (
            "symboltoken",
            None,
        ),
    ],
)
def test_required_text_type_rejected(
    field_name,
    value,
):

    orchestrator, _ = (
        make_orchestrator()
    )

    kwargs = {
        "pipeline_result": (
            make_pipeline_result()
        ),
        "underlying": "NIFTY",
        "exchange": "NSE",
        "symboltoken": "99926000",
    }

    kwargs[
        field_name
    ] = value

    with pytest.raises(
        ValueError,
        match=(
            f"{field_name} must be a string"
        ),
    ):
        orchestrator.process_decision(
            **kwargs
        )


def test_invalid_metadata_rejected():

    orchestrator, _ = (
        make_orchestrator()
    )

    with pytest.raises(
        ValueError,
        match=(
            "metadata must be a dictionary or None"
        ),
    ):
        process_allowed(
            orchestrator,
            metadata=[
                "invalid"
            ],
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "source_decision_id",
        "source_audit_ref",
        "opened_at",
        "trade_id",
    ],
)
def test_optional_empty_text_rejected(
    field_name,
):

    orchestrator, _ = (
        make_orchestrator()
    )

    kwargs = {
        field_name: "",
    }

    with pytest.raises(
        ValueError,
        match=(
            f"{field_name} must not be empty"
        ),
    ):
        process_allowed(
            orchestrator,
            **kwargs,
        )


# ============================================================
# SAFETY BOUNDARY
# ============================================================


def test_non_trade_decision_never_calls_engine():

    orchestrator, engine = (
        make_orchestrator()
    )

    orchestrator.process_decision(
        pipeline_result={
            "decision": "NO_TRADE",
        },
        underlying="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
    )

    assert (
        engine.method_calls
        == []
    )


def test_orchestrator_only_calls_open_trade_for_allowed_decision():

    orchestrator, engine = (
        make_orchestrator()
    )

    process_allowed(
        orchestrator
    )

    method_names = [
        call[0]
        for call in engine.method_calls
    ]

    assert (
        method_names
        == [
            "get_all_trades",
            "open_trade",
        ]
    )

    assert (
        engine.open_trade.call_count
        == 1
    )
    # ============================================================
# HISTORICAL CONTEXT INTEGRATION
# ============================================================


def make_historical_context_orchestrator(
    historical_result=None,
):
    """
    Build an orchestrator with a mocked historical
    context engine.
    """

    engine = MagicMock()

    engine.open_trade.return_value = (
        FakeTrade()
    )

    engine.get_all_trades.return_value = []

    historical_engine = MagicMock()

    if historical_result is not None:
        historical_engine.evaluate.return_value = (
            historical_result
        )

    orchestrator = (
        PaperTradingOrchestrator(
            paper_trading_engine=engine,
            historical_context_engine=(
                historical_engine
            ),
        )
    )

    return (
        orchestrator,
        engine,
        historical_engine,
    )


def test_supportive_historical_context_is_attached():

    historical_result = {
        "historical_bias": "SUPPORTIVE",
        "similar_trades": 10,
        "win_rate": 70.0,
        "expectancy": 100.0,
        "sufficient_sample": True,
    }

    (
        orchestrator,
        engine,
        historical_engine,
    ) = make_historical_context_orchestrator(
        historical_result
    )

    result = process_allowed(
        orchestrator
    )

    metadata = (
        engine.open_trade
        .call_args
        .kwargs["metadata"]
    )

    context = metadata[
        "historical_context"
    ]

    assert result["status"] == "OPENED"

    assert (
        context["historical_bias"]
        == "SUPPORTIVE"
    )

    assert (
        context["advisory_only"]
        is True
    )

    assert (
        context[
            "can_override_live_safety"
        ]
        is False
    )

    historical_engine.evaluate.assert_called_once()


def test_negative_historical_context_does_not_block_trade():

    historical_result = {
        "historical_bias": "NEGATIVE",
        "similar_trades": 20,
        "win_rate": 30.0,
        "expectancy": -50.0,
        "sufficient_sample": True,
    }

    (
        orchestrator,
        engine,
        _,
    ) = make_historical_context_orchestrator(
        historical_result
    )

    result = process_allowed(
        orchestrator
    )

    metadata = (
        engine.open_trade
        .call_args
        .kwargs["metadata"]
    )

    assert result["status"] == "OPENED"
    assert result["opened"] is True

    assert (
        metadata[
            "historical_context"
        ][
            "historical_bias"
        ]
        == "NEGATIVE"
    )

    engine.open_trade.assert_called_once()


def test_insufficient_historical_data_does_not_block_trade():

    historical_result = {
        "historical_bias": (
            "INSUFFICIENT_DATA"
        ),
        "similar_trades": 2,
        "sufficient_sample": False,
    }

    (
        orchestrator,
        engine,
        _,
    ) = make_historical_context_orchestrator(
        historical_result
    )

    result = process_allowed(
        orchestrator
    )

    assert result["status"] == "OPENED"

    engine.open_trade.assert_called_once()


def test_historical_engine_failure_does_not_block_trade():

    (
        orchestrator,
        engine,
        historical_engine,
    ) = make_historical_context_orchestrator()

    historical_engine.evaluate.side_effect = (
        RuntimeError(
            "Historical analysis failed."
        )
    )

    result = process_allowed(
        orchestrator
    )

    metadata = (
        engine.open_trade
        .call_args
        .kwargs["metadata"]
    )

    context = metadata[
        "historical_context"
    ]

    assert result["status"] == "OPENED"

    assert (
        context["historical_bias"]
        == "INSUFFICIENT_DATA"
    )

    assert (
        context["advisory_only"]
        is True
    )

    assert (
        context[
            "can_override_live_safety"
        ]
        is False
    )

    assert (
        "RuntimeError"
        in context["error"]
    )

    engine.open_trade.assert_called_once()


def test_trade_history_failure_does_not_block_trade():

    (
        orchestrator,
        engine,
        _,
    ) = make_historical_context_orchestrator()

    engine.get_all_trades.side_effect = (
        OSError(
            "Trade history unavailable."
        )
    )

    result = process_allowed(
        orchestrator
    )

    metadata = (
        engine.open_trade
        .call_args
        .kwargs["metadata"]
    )

    context = metadata[
        "historical_context"
    ]

    assert result["status"] == "OPENED"

    assert (
        context["historical_bias"]
        == "INSUFFICIENT_DATA"
    )

    assert (
        "OSError"
        in context["error"]
    )

    engine.open_trade.assert_called_once()


def test_custom_historical_engine_cannot_enable_safety_override():

    historical_result = {
        "historical_bias": "NEGATIVE",
        "advisory_only": False,
        "can_override_live_safety": True,
    }

    (
        orchestrator,
        engine,
        _,
    ) = make_historical_context_orchestrator(
        historical_result
    )

    result = process_allowed(
        orchestrator
    )

    context = (
        engine.open_trade
        .call_args
        .kwargs["metadata"][
            "historical_context"
        ]
    )

    assert result["status"] == "OPENED"

    assert (
        context["advisory_only"]
        is True
    )

    assert (
        context[
            "can_override_live_safety"
        ]
        is False
    )


def test_historical_context_receives_trade_history():

    historical_result = {
        "historical_bias": (
            "INSUFFICIENT_DATA"
        ),
    }

    (
        orchestrator,
        engine,
        historical_engine,
    ) = make_historical_context_orchestrator(
        historical_result
    )

    historical_trades = [
        {
            "trade_id": "old-001",
            "status": "CLOSED",
        }
    ]

    engine.get_all_trades.return_value = (
        historical_trades
    )

    process_allowed(
        orchestrator
    )

    call_kwargs = (
        historical_engine.evaluate
        .call_args
        .kwargs
    )

    assert (
        call_kwargs["trades"]
        == historical_trades
    )

    assert isinstance(
        call_kwargs[
            "decision_snapshot"
        ],
        dict,
    )


def test_invalid_historical_result_does_not_block_trade():

    (
        orchestrator,
        engine,
        historical_engine,
    ) = make_historical_context_orchestrator()

    historical_engine.evaluate.return_value = (
        "INVALID"
    )

    result = process_allowed(
        orchestrator
    )

    context = (
        engine.open_trade
        .call_args
        .kwargs["metadata"][
            "historical_context"
        ]
    )

    assert result["status"] == "OPENED"

    assert (
        context["historical_bias"]
        == "INSUFFICIENT_DATA"
    )

    assert (
        context["error"]
        == (
            "INVALID_HISTORICAL_CONTEXT_RESULT"
        )
    )
def test_live_intelligence_propagates_to_historical_context_and_trade_metadata():

    historical_result = {
        "historical_bias": "POSITIVE",
        "similar_trades": 12,
        "sufficient_sample": True,
        "win_rate": 0.75,
        "expectancy": 125.50,
    }

    (
        orchestrator,
        engine,
        historical_engine,
    ) = make_historical_context_orchestrator(
        historical_result
    )

    pipeline_result = (
        make_pipeline_result()
    )

    pipeline_result[
        "market_analysis"
    ] = {
        "strategy": {
            "strategy": (
                "TREND_CONTINUATION"
            ),
            "decision": "TRADE",
            "confidence": 91,
            "risk_flags": [],
        },
        "regime": {
            "primary_regime": (
                "TRENDING_BULLISH"
            ),
            "trend": "BULLISH",
            "confidence": 88,
        },
        "timeframe": {
            "overall_trend": "BULLISH",
            "alignment": "FULL",
            "confidence": 92,
        },
        "technical": {
            "trend": "BULLISH",
            "score": 82,
            "confidence": 86,
        },
        "candlestick": {
            "signal": "BULLISH",
            "patterns": [
                "BULLISH_ENGULFING",
            ],
            "support": 25000.0,
            "resistance": 25200.0,
        },
        "chart": {
            "signal": "BULLISH",
            "patterns": [
                "UPTREND_STRUCTURE",
            ],
        },
        "volume": {
            "bias": "BULLISH",
            "relative_volume": 1.8,
            "volume_spike": True,
            "signals": [
                "VOLUME_SPIKE",
                "BULLISH_VOLUME_CONFIRMATION",
            ],
        },
        "regime_aware_evidence": {
            "contextual_bias": "BULLISH",
            "relevant_signals": [
                "MULTI_TIMEFRAME_TREND",
                "VOLUME_SPIKE",
            ],
            "confirmations": [
                "Volume confirms bullish setup.",
            ],
            "warnings": [],
        },
    }

    result = process_allowed(
        orchestrator,
        pipeline_result=(
            pipeline_result
        ),
    )

    assert result["status"] == "OPENED"

    # --------------------------------------------------------
    # VERIFY DECISION SNAPSHOT REACHES HISTORICAL ENGINE
    # --------------------------------------------------------

    historical_call = (
        historical_engine.evaluate
        .call_args
        .kwargs
    )

    snapshot = historical_call[
        "decision_snapshot"
    ]

    assert (
        snapshot["strategy"]
        == "TREND_CONTINUATION"
    )

    assert (
        snapshot["strategy_confidence"]
        == 91
    )

    assert (
        snapshot["market_regime"]
        == "TRENDING_BULLISH"
    )

    assert (
        snapshot["regime_trend"]
        == "BULLISH"
    )

    assert (
        snapshot["volume_bias"]
        == "BULLISH"
    )

    assert (
        snapshot["relative_volume"]
        == 1.8
    )

    assert (
        snapshot["volume_spike"]
        is True
    )

    assert (
        "VOLUME_SPIKE"
        in snapshot["volume_signals"]
    )

    assert (
        snapshot["contextual_bias"]
        == "BULLISH"
    )

    assert (
        "MULTI_TIMEFRAME_TREND"
        in snapshot["relevant_signals"]
    )

    # --------------------------------------------------------
    # VERIFY SNAPSHOT AND HISTORICAL CONTEXT REACH TRADE
    # METADATA
    # --------------------------------------------------------

    trade_metadata = (
        engine.open_trade
        .call_args
        .kwargs["metadata"]
    )

    assert (
        trade_metadata[
            "decision_snapshot"
        ]["strategy"]
        == "TREND_CONTINUATION"
    )

    assert (
        trade_metadata[
            "decision_snapshot"
        ]["volume_bias"]
        == "BULLISH"
    )

    assert (
        trade_metadata[
            "decision_snapshot"
        ]["contextual_bias"]
        == "BULLISH"
    )

    historical_context = (
        trade_metadata[
            "historical_context"
        ]
    )

    assert (
        historical_context[
            "historical_bias"
        ]
        == "POSITIVE"
    )

    assert (
        historical_context[
            "similar_trades"
        ]
        == 12
    )

    assert (
        historical_context[
            "advisory_only"
        ]
        is True
    )

    assert (
        historical_context[
            "can_override_live_safety"
        ]
        is False
    )

    engine.open_trade.assert_called_once()
    historical_engine.evaluate.assert_called_once()