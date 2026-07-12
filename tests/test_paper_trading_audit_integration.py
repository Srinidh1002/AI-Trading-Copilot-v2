"""
Integration tests for paper-trading lifecycle audit
and optional journal persistence.

These tests verify that:
- opening a paper trade records OPENED
- price updates record PRICE_UPDATED
- stop loss records STOP_LOSS_HIT and CLOSED
- target records TARGET_HIT and CLOSED
- manual exit records CLOSED
- lifecycle event sequences are ordered
- journal persistence is optional
- journal failures never change paper-trade outcomes

This test module is paper-only.
No broker orders are placed.
"""

from unittest.mock import MagicMock

from services.paper_trade import (
    PaperTradeExitReason,
    PaperTradeStatus,
)

from services.paper_trade_journal import (
    PaperTradeJournal,
)

from services.paper_trading_engine import (
    PaperTradingEngine,
)


def make_pipeline_result():
    """
    Build a valid TRADE_ALLOWED pipeline result.
    """

    return {
        "decision": "TRADE_ALLOWED",
        "direction": "BULLISH",
        "contract": {
            "selected": True,
            "symbol": "NIFTY_TEST_CE",
            "option_type": "CE",
            "strike": 24200,
            "expiry": "2026-07-30",
            "premium": 100,
            "lot_size": 75,
        },
        "trade_plan": {
            "allowed": True,
            "levels": {
                "option_entry_price": 100,
                "option_stop_loss": 80,
                "option_target": 140,
            },
            "risk": {
                "allowed": True,
                "lots": 1,
                "quantity": 75,
                "required_capital": 7500,
                "estimated_maximum_loss": 1500,
            },
        },
    }


def open_test_trade(
    engine,
    trade_id="paper-test-1",
):
    """
    Open one deterministic test trade.
    """

    return engine.open_trade(
        pipeline_result=(
            make_pipeline_result()
        ),
        underlying="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
        source_decision_id="decision-001",
        source_audit_ref="audit-001",
        opened_at=(
            "2026-07-12T09:15:00+00:00"
        ),
        metadata={
            "test": True,
        },
        trade_id=trade_id,
    )


def event_names(
    engine,
    trade_id,
):
    """
    Return lifecycle event names for one trade.
    """

    return [
        event["event"]
        for event in (
            engine.get_lifecycle_events(
                trade_id
            )
        )
    ]


def test_open_trade_records_opened_event():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    events = (
        engine.get_lifecycle_events(
            trade.trade_id
        )
    )

    assert len(events) == 1

    assert (
        events[0]["event"]
        == "OPENED"
    )

    assert (
        events[0]["sequence"]
        == 1
    )

    assert (
        events[0]["trade_id"]
        == trade.trade_id
    )

    assert (
        events[0]["status"]
        == PaperTradeStatus.OPEN
    )

    assert (
        events[0]["price"]
        == 100.0
    )


def test_price_update_records_price_updated_event():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    updated = engine.update_price(
        trade_id=trade.trade_id,
        current_price=110,
        updated_at=(
            "2026-07-12T09:20:00+00:00"
        ),
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )

    assert event_names(
        engine,
        trade.trade_id,
    ) == [
        "OPENED",
        "PRICE_UPDATED",
    ]

    latest = (
        engine.get_latest_lifecycle_event(
            trade.trade_id
        )
    )

    assert (
        latest["event"]
        == "PRICE_UPDATED"
    )

    assert (
        latest["price"]
        == 110.0
    )

    assert (
        latest["unrealized_pnl"]
        == 750.0
    )


def test_lifecycle_events_have_sequential_numbers():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    engine.update_price(
        trade.trade_id,
        105,
    )

    engine.update_price(
        trade.trade_id,
        110,
    )

    events = (
        engine.get_lifecycle_events(
            trade.trade_id
        )
    )

    sequences = [
        event["sequence"]
        for event in events
    ]

    assert sequences == [
        1,
        2,
        3,
    ]


def test_stop_loss_records_complete_lifecycle():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=80,
        updated_at=(
            "2026-07-12T09:30:00+00:00"
        ),
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.STOP_LOSS
    )

    assert event_names(
        engine,
        trade.trade_id,
    ) == [
        "OPENED",
        "PRICE_UPDATED",
        "STOP_LOSS_HIT",
        "CLOSED",
    ]


def test_target_records_complete_lifecycle():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=140,
        updated_at=(
            "2026-07-12T10:00:00+00:00"
        ),
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.TARGET
    )

    assert event_names(
        engine,
        trade.trade_id,
    ) == [
        "OPENED",
        "PRICE_UPDATED",
        "TARGET_HIT",
        "CLOSED",
    ]


def test_manual_exit_records_closed_event():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=120,
        exit_reason=(
            PaperTradeExitReason.MANUAL_EXIT
        ),
        closed_at=(
            "2026-07-12T10:30:00+00:00"
        ),
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.MANUAL_EXIT
    )

    assert event_names(
        engine,
        trade.trade_id,
    ) == [
        "OPENED",
        "CLOSED",
    ]


def test_lifecycle_summary_matches_events():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    engine.update_price(
        trade.trade_id,
        110,
    )

    summary = (
        engine.get_lifecycle_summary(
            trade.trade_id
        )
    )

    assert (
        summary["trade_id"]
        == trade.trade_id
    )

    assert (
        summary["event_count"]
        == 2
    )

    assert (
        summary["latest_event"]
        == "PRICE_UPDATED"
    )

    assert (
        summary["latest_status"]
        == "OPEN"
    )

    assert len(
        summary["events"]
    ) == 2


def test_lifecycle_events_are_defensive_copies():

    engine = PaperTradingEngine()

    trade = open_test_trade(
        engine
    )

    events = (
        engine.get_lifecycle_events(
            trade.trade_id
        )
    )

    events[0][
        "event"
    ] = "CORRUPTED"

    fresh_events = (
        engine.get_lifecycle_events(
            trade.trade_id
        )
    )

    assert (
        fresh_events[0]["event"]
        == "OPENED"
    )


def test_journal_persistence_disabled_by_default():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
    )

    trade = open_test_trade(
        engine
    )

    journal.log.assert_not_called()

    assert (
        engine.get_journal_status(
            trade.trade_id
        )
        == {
            "enabled": False,
            "persisted": False,
            "error": None,
        }
    )


def test_enabled_journal_persists_open_event():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    journal.log.assert_called_once()

    call_kwargs = (
        journal.log.call_args.kwargs
    )

    assert (
        call_kwargs[
            "lifecycle_event"
        ][
            "event"
        ]
        == "OPENED"
    )

    assert (
        call_kwargs[
            "lifecycle_event"
        ][
            "trade_id"
        ]
        == trade.trade_id
    )

    status = (
        engine.get_journal_status(
            trade.trade_id
        )
    )

    assert (
        status["enabled"]
        is True
    )

    assert (
        status["persisted"]
        is True
    )

    assert (
        status["error"]
        is None
    )


def test_journal_receives_trade_metadata():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    open_test_trade(
        engine
    )

    metadata = (
        journal.log
        .call_args
        .kwargs[
            "metadata"
        ]
    )

    assert (
        metadata["underlying"]
        == "NIFTY"
    )

    assert (
        metadata["exchange"]
        == "NSE"
    )

    assert (
        metadata["option_symbol"]
        == "NIFTY_TEST_CE"
    )

    assert (
        metadata["option_type"]
        == "CE"
    )

    assert (
        metadata["source_decision_id"]
        == "decision-001"
    )


def test_price_update_is_persisted():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    engine.update_price(
        trade.trade_id,
        110,
    )

    assert (
        journal.log.call_count
        == 2
    )

    latest_event = (
        journal.log
        .call_args
        .kwargs[
            "lifecycle_event"
        ]
    )

    assert (
        latest_event["event"]
        == "PRICE_UPDATED"
    )


def test_stop_loss_persists_all_lifecycle_events():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    engine.update_price(
        trade.trade_id,
        80,
    )

    persisted_events = [
        call.kwargs[
            "lifecycle_event"
        ][
            "event"
        ]
        for call in (
            journal.log.call_args_list
        )
    ]

    assert persisted_events == [
        "OPENED",
        "PRICE_UPDATED",
        "STOP_LOSS_HIT",
        "CLOSED",
    ]


def test_target_persists_all_lifecycle_events():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    engine.update_price(
        trade.trade_id,
        140,
    )

    persisted_events = [
        call.kwargs[
            "lifecycle_event"
        ][
            "event"
        ]
        for call in (
            journal.log.call_args_list
        )
    ]

    assert persisted_events == [
        "OPENED",
        "PRICE_UPDATED",
        "TARGET_HIT",
        "CLOSED",
    ]


def test_journal_failure_does_not_block_open():

    journal = MagicMock()

    journal.log.side_effect = OSError(
        "Disk unavailable."
    )

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    assert (
        trade.status
        == PaperTradeStatus.OPEN
    )

    assert (
        engine.count_open_trades()
        == 1
    )

    status = (
        engine.get_journal_status(
            trade.trade_id
        )
    )

    assert (
        status["enabled"]
        is True
    )

    assert (
        status["persisted"]
        is False
    )

    assert (
        status["error"]
        == "Disk unavailable."
    )


def test_journal_failure_does_not_block_price_update():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    journal.log.side_effect = RuntimeError(
        "Journal unavailable."
    )

    updated = engine.update_price(
        trade.trade_id,
        110,
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )

    assert (
        updated.current_price
        == 110.0
    )

    assert (
        updated.unrealized_pnl
        == 750.0
    )

    status = (
        engine.get_journal_status(
            trade.trade_id
        )
    )

    assert (
        status["persisted"]
        is False
    )

    assert (
        status["error"]
        == "Journal unavailable."
    )


def test_journal_failure_does_not_block_stop_loss_close():

    journal = MagicMock()

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    journal.log.side_effect = OSError(
        "Write failed."
    )

    closed = engine.update_price(
        trade.trade_id,
        80,
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.STOP_LOSS
    )

    assert event_names(
        engine,
        trade.trade_id,
    ) == [
        "OPENED",
        "PRICE_UPDATED",
        "STOP_LOSS_HIT",
        "CLOSED",
    ]


def test_real_journal_writes_lifecycle_events(
    tmp_path,
):

    journal_path = (
        tmp_path
        / "paper_trade_journal.jsonl"
    )

    journal = PaperTradeJournal(
        file_path=journal_path,
    )

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    engine.update_price(
        trade.trade_id,
        110,
    )

    records = (
        journal.read_records()
    )

    assert len(records) == 2

    assert [
        record["event"]
        for record in records
    ] == [
        "OPENED",
        "PRICE_UPDATED",
    ]

    assert all(
        record["trade_id"]
        == trade.trade_id
        for record in records
    )


def test_real_journal_records_complete_target_lifecycle(
    tmp_path,
):

    journal = PaperTradeJournal(
        file_path=(
            tmp_path
            / "target_lifecycle.jsonl"
        ),
    )

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    engine.update_price(
        trade.trade_id,
        140,
    )

    records = (
        journal.read_records()
    )

    assert [
        record["event"]
        for record in records
    ] == [
        "OPENED",
        "PRICE_UPDATED",
        "TARGET_HIT",
        "CLOSED",
    ]


def test_persistence_cannot_change_trade_state():

    journal = MagicMock()

    journal.log.return_value = {
        "status": "CLOSED",
        "event": "CLOSED",
        "realized_pnl": 999999,
    }

    engine = PaperTradingEngine(
        journal=journal,
        persist_journal=True,
    )

    trade = open_test_trade(
        engine
    )

    assert (
        trade.status
        == PaperTradeStatus.OPEN
    )

    assert (
        trade.realized_pnl
        is None
    )

    assert (
        trade.current_price
        == 100.0
    )