"""
Integration tests for paper-trading restart recovery.

Uses the real:
- PaperTradeRepository
- PaperTradingEngine
- PaperTradingRecoveryManager

No broker connection is used.
No real order is placed.
"""

from services.paper_trade_repository import (
    PaperTradeRepository,
)
from services.paper_trading_engine import (
    PaperTradingEngine,
)
from services.paper_trading_recovery_manager import (
    PaperTradingRecoveryManager,
)


def make_pipeline_result():
    return {
        "decision": "TRADE_ALLOWED",
        "direction": "BULLISH",
        "contract": {
            "selected": True,
            "symbol": "NIFTY_TEST_CE",
            "option_type": "CE",
            "strike": 25000.0,
            "expiry": "2026-07-30",
            "premium": 100.0,
            "lot_size": 75,
        },
        "trade_plan": {
            "allowed": True,
            "levels": {
                "option_entry_price": 100.0,
                "option_stop_loss": 90.0,
                "option_target": 120.0,
            },
            "risk": {
                "allowed": True,
                "lots": 1,
                "quantity": 75,
                "required_capital": 7500.0,
                "estimated_maximum_loss": 750.0,
            },
        },
    }


def make_repository(file_path):
    return PaperTradeRepository(
        file_path=file_path
    )


def make_engine(repository):
    return PaperTradingEngine(
        repository=repository,
        persist_state=True,
    )


def test_open_trade_survives_simulated_restart(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    repository_before = make_repository(
        file_path
    )

    engine_before = make_engine(
        repository_before
    )

    opened_trade = engine_before.open_trade(
        make_pipeline_result(),
        underlying="NIFTY",
        exchange="NFO",
        symboltoken="123456",
        source_decision_id="decision-1",
        source_audit_ref="audit-1",
        trade_id="restart-open-1",
    )

    assert (
        opened_trade.trade_id
        == "restart-open-1"
    )

    assert (
        opened_trade.status
        == "OPEN"
    )

    assert file_path.exists()

    # Simulate application restart with
    # completely new repository and engine instances.

    repository_after = make_repository(
        file_path
    )

    engine_after = make_engine(
        repository_after
    )

    manager = (
        PaperTradingRecoveryManager(
            engine_after,
            include_closed=True,
        )
    )

    result = manager.recover()

    assert result["success"] is True
    assert result["status"] == "RECOVERED"
    assert result["recovered_count"] == 1
    assert result["open_count"] == 1
    assert result["closed_count"] == 0

    recovered = result[
        "open_trades"
    ][0]

    assert (
        recovered["trade_id"]
        == "restart-open-1"
    )

    assert (
        recovered["status"]
        == "OPEN"
    )

    assert (
        recovered["underlying"]
        == "NIFTY"
    )

    assert (
        recovered["symboltoken"]
        == "123456"
    )

    assert (
        recovered["source_decision_id"]
        == "decision-1"
    )


def test_closed_trade_survives_simulated_restart(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    repository_before = make_repository(
        file_path
    )

    engine_before = make_engine(
        repository_before
    )

    engine_before.open_trade(
        make_pipeline_result(),
        underlying="NIFTY",
        exchange="NFO",
        symboltoken="123456",
        trade_id="restart-closed-1",
    )

    closed_trade = (
        engine_before.close_trade(
            "restart-closed-1",
            exit_price=115.0,
            exit_reason="TARGET",
        )
    )

    assert (
        closed_trade.status
        == "CLOSED"
    )

    repository_after = make_repository(
        file_path
    )

    engine_after = make_engine(
        repository_after
    )

    manager = (
        PaperTradingRecoveryManager(
            engine_after,
            include_closed=True,
        )
    )

    result = manager.recover()

    assert result["success"] is True
    assert result["recovered_count"] == 1
    assert result["open_count"] == 0
    assert result["closed_count"] == 1

    recovered = result[
        "closed_trades"
    ][0]

    assert (
        recovered["trade_id"]
        == "restart-closed-1"
    )

    assert (
        recovered["status"]
        == "CLOSED"
    )

    assert (
        recovered["exit_price"]
        == 115.0
    )

    assert (
        recovered["exit_reason"]
        == "TARGET"
    )


def test_multiple_trades_survive_restart(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    repository_before = make_repository(
        file_path
    )

    engine_before = make_engine(
        repository_before
    )

    engine_before.open_trade(
        make_pipeline_result(),
        underlying="NIFTY",
        exchange="NFO",
        symboltoken="111",
        trade_id="trade-open",
    )

    engine_before.open_trade(
        make_pipeline_result(),
        underlying="BANKNIFTY",
        exchange="NFO",
        symboltoken="222",
        trade_id="trade-closed",
    )

    engine_before.close_trade(
        "trade-closed",
        exit_price=95.0,
        exit_reason="STOP_LOSS",
    )

    repository_after = make_repository(
        file_path
    )

    engine_after = make_engine(
        repository_after
    )

    manager = (
        PaperTradingRecoveryManager(
            engine_after
        )
    )

    result = manager.recover()

    assert result["success"] is True
    assert result["recovered_count"] == 2
    assert result["open_count"] == 1
    assert result["closed_count"] == 1

    assert {
        trade["trade_id"]
        for trade in result[
            "recovered_trades"
        ]
    } == {
        "trade-open",
        "trade-closed",
    }


def test_recovered_open_trade_can_continue_updating(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    engine_before = make_engine(
        make_repository(
            file_path
        )
    )

    engine_before.open_trade(
        make_pipeline_result(),
        underlying="NIFTY",
        exchange="NFO",
        symboltoken="123456",
        trade_id="continue-1",
    )

    engine_after = make_engine(
        make_repository(
            file_path
        )
    )

    manager = (
        PaperTradingRecoveryManager(
            engine_after
        )
    )

    recovery = manager.recover()

    assert (
        recovery["open_count"]
        == 1
    )

    updated_trade = (
        engine_after.update_price(
            "continue-1",
            current_price=105.0,
            auto_close=False,
        )
    )

    assert (
        updated_trade.status
        == "OPEN"
    )

    assert (
        updated_trade.current_price
        == 105.0
    )

    # Simulate another restart and verify
    # the updated state was persisted.

    final_engine = make_engine(
        make_repository(
            file_path
        )
    )

    final_recovery = (
        PaperTradingRecoveryManager(
            final_engine
        ).recover()
    )

    assert (
        final_recovery["open_count"]
        == 1
    )

    final_trade = final_recovery[
        "open_trades"
    ][0]

    assert (
        final_trade["current_price"]
        == 105.0
    )


def test_include_closed_false_recovers_only_open_trades(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    engine_before = make_engine(
        make_repository(
            file_path
        )
    )

    engine_before.open_trade(
        make_pipeline_result(),
        underlying="NIFTY",
        exchange="NFO",
        symboltoken="111",
        trade_id="open-only",
    )

    engine_before.open_trade(
        make_pipeline_result(),
        underlying="BANKNIFTY",
        exchange="NFO",
        symboltoken="222",
        trade_id="closed-hidden",
    )

    engine_before.close_trade(
        "closed-hidden",
        exit_price=110.0,
    )

    engine_after = make_engine(
        make_repository(
            file_path
        )
    )

    result = (
        PaperTradingRecoveryManager(
            engine_after,
            include_closed=False,
        ).recover()
    )

    assert result["success"] is True
    assert result["recovered_count"] == 1
    assert result["open_count"] == 1
    assert result["closed_count"] == 0

    assert (
        result[
            "open_trades"
        ][0][
            "trade_id"
        ]
        == "open-only"
    )


def test_empty_repository_after_restart_is_safe(
    tmp_path,
):
    file_path = (
        tmp_path
        / "paper_trades.json"
    )

    engine = make_engine(
        make_repository(
            file_path
        )
    )

    result = (
        PaperTradingRecoveryManager(
            engine
        ).recover()
    )

    assert result["success"] is True
    assert result["status"] == "EMPTY"
    assert result["recovered_count"] == 0
    assert result["open_count"] == 0
    assert result["closed_count"] == 0