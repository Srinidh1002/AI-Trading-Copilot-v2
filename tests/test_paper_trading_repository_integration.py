"""
Integration tests for PaperTradingEngine and
PaperTradeRepository.

Verifies:
- OPEN state persistence
- price update persistence
- manual close persistence
- stop-loss persistence
- target persistence
- restart recovery
- OPEN/CLOSED recovery
- recovery filtering
- duplicate recovery protection
- repository failure isolation
- corrupted repository fail-closed behavior
- defensive-copy behavior

Paper trading only.
No broker orders are placed.
"""

import json
from unittest.mock import MagicMock

import pytest

from services.paper_trade import (
    PaperTradeExitReason,
    PaperTradeStatus,
)

from services.paper_trade_repository import (
    PaperTradeRepository,
)

from services.paper_trading_engine import (
    PaperTradingEngine,
)


# ============================================================
# HELPERS
# ============================================================


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
            "strike": 24200.0,
            "premium": 100.0,
            "lot_size": 75,
            "expiry": "2026-07-30",
        },
        "trade_plan": {
            "allowed": True,
            "decision": "TRADE_ALLOWED",
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


def make_engine(
    tmp_path,
    persist_state=True,
):
    """
    Build an engine with a real temporary repository.
    """

    repository = (
        PaperTradeRepository(
            tmp_path
            / "paper_trade_state.json"
        )
    )

    engine = (
        PaperTradingEngine(
            repository=repository,
            persist_state=persist_state,
        )
    )

    return (
        engine,
        repository,
    )


def open_test_trade(
    engine,
    trade_id="paper-integration-001",
):
    """
    Open one deterministic paper trade.
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
            "integration_test": True,
        },
        trade_id=trade_id,
    )


# ============================================================
# OPEN PERSISTENCE
# ============================================================


def test_open_trade_is_persisted(
    tmp_path,
):

    engine, repository = (
        make_engine(
            tmp_path
        )
    )

    trade = open_test_trade(
        engine
    )

    persisted = (
        repository.get_trade(
            trade.trade_id
        )
    )

    assert persisted is not None

    assert (
        persisted["trade_id"]
        == trade.trade_id
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.OPEN
    )


def test_open_trade_repository_status_success(
    tmp_path,
):

    engine, _ = (
        make_engine(
            tmp_path
        )
    )

    trade = open_test_trade(
        engine
    )

    status = (
        engine.get_repository_status(
            trade.trade_id
        )
    )

    assert status == {
        "enabled": True,
        "persisted": True,
        "error": None,
    }


def test_persistence_disabled_does_not_write(
    tmp_path,
):

    engine, repository = (
        make_engine(
            tmp_path,
            persist_state=False,
        )
    )

    trade = open_test_trade(
        engine
    )

    assert (
        repository.get_trade(
            trade.trade_id
        )
        is None
    )

    assert (
        engine.get_repository_status(
            trade.trade_id
        )
        == {
            "enabled": False,
            "persisted": False,
            "error": None,
        }
    )


# ============================================================
# PRICE UPDATE PERSISTENCE
# ============================================================


def test_price_update_is_persisted(
    tmp_path,
):

    engine, repository = (
        make_engine(
            tmp_path
        )
    )

    trade = open_test_trade(
        engine
    )

    updated = (
        engine.update_price(
            trade_id=trade.trade_id,
            current_price=120.0,
            updated_at=(
                "2026-07-12T09:30:00+00:00"
            ),
        )
    )

    persisted = (
        repository.get_trade(
            trade.trade_id
        )
    )

    assert (
        persisted["current_price"]
        == 120.0
    )

    assert (
        persisted["unrealized_pnl"]
        == updated.unrealized_pnl
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.OPEN
    )


# ============================================================
# CLOSE PERSISTENCE
# ============================================================


def test_manual_close_is_persisted(
    tmp_path,
):

    engine, repository = (
        make_engine(
            tmp_path
        )
    )

    trade = open_test_trade(
        engine
    )

    closed = (
        engine.close_trade(
            trade_id=trade.trade_id,
            exit_price=120.0,
            exit_reason=(
                PaperTradeExitReason
                .MANUAL_EXIT
            ),
            closed_at=(
                "2026-07-12T10:00:00+00:00"
            ),
        )
    )

    persisted = (
        repository.get_trade(
            trade.trade_id
        )
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["exit_price"]
        == 120.0
    )

    assert (
        persisted["exit_reason"]
        == PaperTradeExitReason.MANUAL_EXIT
    )

    assert (
        persisted["realized_pnl"]
        == closed.realized_pnl
    )


def test_stop_loss_close_is_persisted(
    tmp_path,
):

    engine, repository = (
        make_engine(
            tmp_path
        )
    )

    trade = open_test_trade(
        engine
    )

    closed = (
        engine.update_price(
            trade_id=trade.trade_id,
            current_price=80.0,
            updated_at=(
                "2026-07-12T10:00:00+00:00"
            ),
        )
    )

    persisted = (
        repository.get_trade(
            trade.trade_id
        )
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["exit_reason"]
        == PaperTradeExitReason.STOP_LOSS
    )


def test_target_close_is_persisted(
    tmp_path,
):

    engine, repository = (
        make_engine(
            tmp_path
        )
    )

    trade = open_test_trade(
        engine
    )

    closed = (
        engine.update_price(
            trade_id=trade.trade_id,
            current_price=140.0,
            updated_at=(
                "2026-07-12T10:00:00+00:00"
            ),
        )
    )

    persisted = (
        repository.get_trade(
            trade.trade_id
        )
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["status"]
        == PaperTradeStatus.CLOSED
    )

    assert (
        persisted["exit_reason"]
        == PaperTradeExitReason.TARGET
    )


# ============================================================
# RESTART RECOVERY
# ============================================================


def test_new_engine_recovers_open_trade(
    tmp_path,
):

    file_path = (
        tmp_path
        / "paper_trade_state.json"
    )

    repository_one = (
        PaperTradeRepository(
            file_path
        )
    )

    engine_one = (
        PaperTradingEngine(
            repository=repository_one,
            persist_state=True,
        )
    )

    original = open_test_trade(
        engine_one,
        trade_id="restart-open",
    )

    engine_one.update_price(
        trade_id=original.trade_id,
        current_price=120.0,
        updated_at=(
            "2026-07-12T09:30:00+00:00"
        ),
    )

    repository_two = (
        PaperTradeRepository(
            file_path
        )
    )

    engine_two = (
        PaperTradingEngine(
            repository=repository_two,
            persist_state=True,
        )
    )

    recovered = (
        engine_two.recover_trades()
    )

    assert len(
        recovered
    ) == 1

    recovered_trade = (
        engine_two.get_trade(
            "restart-open"
        )
    )

    assert (
        recovered_trade.trade_id
        == "restart-open"
    )

    assert (
        recovered_trade.status
        == PaperTradeStatus.OPEN
    )

    assert (
        recovered_trade.current_price
        == 120.0
    )


def test_recovered_open_trade_can_continue_updating(
    tmp_path,
):

    file_path = (
        tmp_path
        / "paper_trade_state.json"
    )

    first_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    open_test_trade(
        first_engine,
        trade_id="continue-after-restart",
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    second_engine.recover_trades()

    updated = (
        second_engine.update_price(
            trade_id=(
                "continue-after-restart"
            ),
            current_price=125.0,
        )
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )

    assert (
        updated.current_price
        == 125.0
    )


def test_recovered_open_trade_can_close(
    tmp_path,
):

    file_path = (
        tmp_path
        / "paper_trade_state.json"
    )

    first_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    open_test_trade(
        first_engine,
        trade_id="close-after-restart",
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    second_engine.recover_trades()

    closed = (
        second_engine.close_trade(
            trade_id=(
                "close-after-restart"
            ),
            exit_price=120.0,
        )
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )


def test_recover_open_and_closed_trades(
    tmp_path,
):

    file_path = (
        tmp_path
        / "paper_trade_state.json"
    )

    first_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    open_test_trade(
        first_engine,
        trade_id="open-trade",
    )

    closed_trade = open_test_trade(
        first_engine,
        trade_id="closed-trade",
    )

    first_engine.close_trade(
        trade_id=closed_trade.trade_id,
        exit_price=120.0,
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    recovered = (
        second_engine.recover_trades(
            include_closed=True
        )
    )

    assert len(
        recovered
    ) == 2

    assert (
        second_engine.count_open_trades()
        == 1
    )

    assert (
        second_engine.count_closed_trades()
        == 1
    )


def test_recover_only_open_trades(
    tmp_path,
):

    file_path = (
        tmp_path
        / "paper_trade_state.json"
    )

    first_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    open_test_trade(
        first_engine,
        trade_id="open-only",
    )

    closed_trade = open_test_trade(
        first_engine,
        trade_id="closed-excluded",
    )

    first_engine.close_trade(
        trade_id=closed_trade.trade_id,
        exit_price=120.0,
    )

    second_engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    recovered = (
        second_engine.recover_trades(
            include_closed=False
        )
    )

    assert len(
        recovered
    ) == 1

    assert (
        recovered[0].trade_id
        == "open-only"
    )

    assert (
        second_engine.count_trades()
        == 1
    )


# ============================================================
# DUPLICATE RECOVERY PROTECTION
# ============================================================


def test_recovering_same_trade_twice_is_rejected(
    tmp_path,
):

    engine, _ = (
        make_engine(
            tmp_path
        )
    )

    open_test_trade(
        engine,
        trade_id="duplicate-recovery",
    )

    second_engine = (
        PaperTradingEngine(
            repository=engine.repository,
            persist_state=True,
        )
    )

    second_engine.recover_trades()

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        second_engine.recover_trades()


# ============================================================
# REPOSITORY FAILURE ISOLATION
# ============================================================


def test_repository_failure_does_not_block_open_trade():

    repository = MagicMock()

    repository.save_trade.side_effect = (
        OSError(
            "Disk unavailable."
        )
    )

    engine = (
        PaperTradingEngine(
            repository=repository,
            persist_state=True,
        )
    )

    trade = open_test_trade(
        engine,
        trade_id="open-despite-failure",
    )

    assert (
        trade.status
        == PaperTradeStatus.OPEN
    )

    assert (
        engine.count_trades()
        == 1
    )

    status = (
        engine.get_repository_status(
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


def test_repository_failure_does_not_block_price_update():

    repository = MagicMock()

    engine = (
        PaperTradingEngine(
            repository=repository,
            persist_state=True,
        )
    )

    trade = open_test_trade(
        engine,
        trade_id="update-despite-failure",
    )

    repository.save_trade.side_effect = (
        OSError(
            "Disk unavailable."
        )
    )

    updated = (
        engine.update_price(
            trade_id=trade.trade_id,
            current_price=120.0,
        )
    )

    assert (
        updated.current_price
        == 120.0
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )


def test_repository_failure_does_not_block_close():

    repository = MagicMock()

    engine = (
        PaperTradingEngine(
            repository=repository,
            persist_state=True,
        )
    )

    trade = open_test_trade(
        engine,
        trade_id="close-despite-failure",
    )

    repository.save_trade.side_effect = (
        OSError(
            "Disk unavailable."
        )
    )

    closed = (
        engine.close_trade(
            trade_id=trade.trade_id,
            exit_price=120.0,
        )
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_price
        == 120.0
    )


# ============================================================
# FAIL-CLOSED RECOVERY
# ============================================================


def test_recovery_without_repository_is_rejected():

    engine = (
        PaperTradingEngine()
    )

    with pytest.raises(
        ValueError,
        match="no repository",
    ):
        engine.recover_trades()


def test_corrupted_repository_recovery_fails_closed(
    tmp_path,
):

    file_path = (
        tmp_path
        / "paper_trade_state.json"
    )

    file_path.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    engine = (
        PaperTradingEngine(
            repository=(
                PaperTradeRepository(
                    file_path
                )
            ),
            persist_state=True,
        )
    )

    with pytest.raises(
        ValueError,
        match="Invalid JSON",
    ):
        engine.recover_trades()

    assert (
        engine.count_trades()
        == 0
    )


# ============================================================
# DEFENSIVE COPY
# ============================================================


def test_recovered_trade_is_defensive_copy(
    tmp_path,
):

    engine_one, repository = (
        make_engine(
            tmp_path
        )
    )

    open_test_trade(
        engine_one,
        trade_id="defensive-recovery",
    )

    engine_two = (
        PaperTradingEngine(
            repository=repository,
            persist_state=True,
        )
    )

    recovered = (
        engine_two.recover_trades()
    )

    recovered[0].current_price = (
        999999.0
    )

    stored = (
        engine_two.get_trade(
            "defensive-recovery"
        )
    )

    assert (
        stored.current_price
        == 100.0
    )