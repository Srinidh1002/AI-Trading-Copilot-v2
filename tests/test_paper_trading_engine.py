"""
Tests for the paper trading lifecycle engine.

These tests verify simulated paper-trade lifecycle behavior only.
No broker connection or real order execution is involved.
"""

from copy import deepcopy

import pytest

from services.paper_trade import (
    PaperTradeExitReason,
    PaperTradeStatus,
)

from services.paper_trading_engine import (
    PaperTradingEngine,
)


# ---------------------------------
# TEST DATA HELPERS
# ---------------------------------


def make_pipeline_result(
    decision="TRADE_ALLOWED",
    direction="BULLISH",
    option_type="CE",
    entry_price=100.0,
    stop_loss=80.0,
    target=140.0,
    premium=100.0,
    lot_size=75,
    lots=1,
):
    quantity = (
        lot_size
        * lots
    )

    return {
        "decision": decision,
        "direction": direction,
        "contract": {
            "selected": True,
            "symbol": (
                "NIFTY24JUL24200CE"
                if option_type == "CE"
                else "NIFTY24JUL24200PE"
            ),
            "option_type": option_type,
            "strike": 24200,
            "expiry": "2026-07-30",
            "premium": premium,
            "lot_size": lot_size,
        },
        "trade_plan": {
            "allowed": True,
            "levels": {
                "option_entry_price": (
                    entry_price
                ),
                "option_stop_loss": (
                    stop_loss
                ),
                "option_target": (
                    target
                ),
            },
            "risk": {
                "allowed": True,
                "lots": lots,
                "quantity": quantity,
                "required_capital": (
                    entry_price
                    * quantity
                ),
                "estimated_maximum_loss": (
                    (
                        entry_price
                        - stop_loss
                    )
                    * quantity
                ),
            },
        },
    }


def open_trade(
    engine=None,
    trade_id="paper-001",
    **pipeline_kwargs,
):
    if engine is None:
        engine = (
            PaperTradingEngine()
        )

    result = (
        make_pipeline_result(
            **pipeline_kwargs
        )
    )

    trade = engine.open_trade(
        pipeline_result=result,
        underlying="NIFTY",
        exchange="NSE",
        symboltoken="99926000",
        trade_id=trade_id,
        opened_at=(
            "2026-07-12T10:00:00+00:00"
        ),
    )

    return (
        engine,
        trade,
    )


# ---------------------------------
# INITIALIZATION
# ---------------------------------


def test_engine_starts_empty():
    engine = (
        PaperTradingEngine()
    )

    assert (
        engine.count_trades()
        == 0
    )

    assert (
        engine.count_open_trades()
        == 0
    )

    assert (
        engine.count_closed_trades()
        == 0
    )


# ---------------------------------
# OPEN TRADE
# ---------------------------------


def test_open_trade_creates_open_position():
    engine, trade = (
        open_trade()
    )

    assert (
        trade.status
        == PaperTradeStatus.OPEN
    )

    assert (
        trade.trade_id
        == "paper-001"
    )

    assert (
        engine.count_trades()
        == 1
    )


def test_open_trade_contains_market_identity():
    _, trade = (
        open_trade()
    )

    assert (
        trade.underlying
        == "NIFTY"
    )

    assert (
        trade.exchange
        == "NSE"
    )

    assert (
        trade.symboltoken
        == "99926000"
    )


def test_open_trade_contains_contract_details():
    _, trade = (
        open_trade()
    )

    assert (
        trade.option_type
        == "CE"
    )

    assert (
        trade.strike
        == 24200
    )

    assert (
        trade.entry_price
        == 100.0
    )

    assert (
        trade.stop_loss_price
        == 80.0
    )

    assert (
        trade.target_price
        == 140.0
    )


def test_open_trade_calculates_quantity():
    _, trade = (
        open_trade(
            lot_size=75,
            lots=2,
        )
    )

    assert (
        trade.quantity
        == 150
    )


def test_open_trade_initial_current_price_is_entry():
    _, trade = (
        open_trade()
    )

    assert (
        trade.current_price
        == trade.entry_price
    )


def test_open_trade_initial_unrealized_pnl_is_zero():
    _, trade = (
        open_trade()
    )

    assert (
        trade.unrealized_pnl
        == 0.0
    )


def test_open_trade_rejects_non_allowed_decision():
    engine = (
        PaperTradingEngine()
    )

    result = (
        make_pipeline_result(
            decision="NO_TRADE"
        )
    )

    with pytest.raises(
        ValueError
    ):
        engine.open_trade(
            pipeline_result=result,
            underlying="NIFTY",
            exchange="NSE",
        )


def test_duplicate_trade_id_rejected():
    engine, _ = (
        open_trade()
    )

    with pytest.raises(
        ValueError
    ):
        engine.open_trade(
            pipeline_result=(
                make_pipeline_result()
            ),
            underlying="NIFTY",
            exchange="NSE",
            trade_id="paper-001",
        )


def test_auto_generated_trade_id_is_created():
    engine = (
        PaperTradingEngine()
    )

    trade = engine.open_trade(
        pipeline_result=(
            make_pipeline_result()
        ),
        underlying="NIFTY",
        exchange="NSE",
    )

    assert isinstance(
        trade.trade_id,
        str,
    )

    assert (
        trade.trade_id.strip()
    )


def test_open_trade_preserves_source_references():
    engine = (
        PaperTradingEngine()
    )

    trade = engine.open_trade(
        pipeline_result=(
            make_pipeline_result()
        ),
        underlying="NIFTY",
        exchange="NSE",
        source_decision_id=(
            "decision-123"
        ),
        source_audit_ref=(
            "audit-456"
        ),
    )

    assert (
        trade.source_decision_id
        == "decision-123"
    )

    assert (
        trade.source_audit_ref
        == "audit-456"
    )


def test_open_trade_metadata_is_defensively_copied():
    engine = (
        PaperTradingEngine()
    )

    metadata = {
        "nested": {
            "value": 1
        }
    }

    trade = engine.open_trade(
        pipeline_result=(
            make_pipeline_result()
        ),
        underlying="NIFTY",
        exchange="NSE",
        metadata=metadata,
    )

    metadata[
        "nested"
    ][
        "value"
    ] = 999

    assert (
        trade.metadata[
            "nested"
        ][
            "value"
        ]
        == 1
    )


# ---------------------------------
# GET TRADE
# ---------------------------------


def test_get_trade_returns_trade():
    engine, opened = (
        open_trade()
    )

    fetched = engine.get_trade(
        opened.trade_id
    )

    assert (
        fetched.trade_id
        == opened.trade_id
    )


def test_get_missing_trade_rejected():
    engine = (
        PaperTradingEngine()
    )

    with pytest.raises(
        ValueError
    ):
        engine.get_trade(
            "missing-trade"
        )


def test_get_trade_returns_defensive_copy():
    engine, opened = (
        open_trade()
    )

    fetched = engine.get_trade(
        opened.trade_id
    )

    fetched.current_price = 999

    stored = engine.get_trade(
        opened.trade_id
    )

    assert (
        stored.current_price
        == 100.0
    )


# ---------------------------------
# LIST TRADES
# ---------------------------------


def test_get_all_trades_returns_all():
    engine = (
        PaperTradingEngine()
    )

    open_trade(
        engine=engine,
        trade_id="paper-001",
    )

    open_trade(
        engine=engine,
        trade_id="paper-002",
    )

    trades = (
        engine.get_all_trades()
    )

    assert (
        len(
            trades
        )
        == 2
    )


def test_get_all_trades_returns_copies():
    engine, _ = (
        open_trade()
    )

    trades = (
        engine.get_all_trades()
    )

    trades[
        0
    ].current_price = 999

    stored = engine.get_trade(
        "paper-001"
    )

    assert (
        stored.current_price
        == 100.0
    )


def test_get_open_trades_only_returns_open():
    engine = (
        PaperTradingEngine()
    )

    open_trade(
        engine=engine,
        trade_id="paper-001",
    )

    open_trade(
        engine=engine,
        trade_id="paper-002",
    )

    engine.close_trade(
        trade_id="paper-002",
        exit_price=110,
    )

    open_trades = (
        engine.get_open_trades()
    )

    assert (
        len(
            open_trades
        )
        == 1
    )

    assert (
        open_trades[
            0
        ].trade_id
        == "paper-001"
    )


def test_get_closed_trades_only_returns_closed():
    engine = (
        PaperTradingEngine()
    )

    open_trade(
        engine=engine,
        trade_id="paper-001",
    )

    open_trade(
        engine=engine,
        trade_id="paper-002",
    )

    engine.close_trade(
        trade_id="paper-002",
        exit_price=110,
    )

    closed_trades = (
        engine.get_closed_trades()
    )

    assert (
        len(
            closed_trades
        )
        == 1
    )

    assert (
        closed_trades[
            0
        ].trade_id
        == "paper-002"
    )


# ---------------------------------
# PRICE UPDATE
# ---------------------------------


def test_update_price_changes_current_price():
    engine, trade = (
        open_trade()
    )

    updated = engine.update_price(
        trade_id=trade.trade_id,
        current_price=110,
        auto_close=False,
    )

    assert (
        updated.current_price
        == 110.0
    )


def test_update_price_calculates_profit():
    engine, trade = (
        open_trade()
    )

    updated = engine.update_price(
        trade_id=trade.trade_id,
        current_price=110,
        auto_close=False,
    )

    assert (
        updated.unrealized_pnl
        == 750.0
    )


def test_update_price_calculates_loss():
    engine, trade = (
        open_trade()
    )

    updated = engine.update_price(
        trade_id=trade.trade_id,
        current_price=90,
        auto_close=False,
    )

    assert (
        updated.unrealized_pnl
        == -750.0
    )


@pytest.mark.parametrize(
    "invalid_price",
    [
        None,
        0,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        "",
        "invalid",
    ],
)
def test_update_rejects_invalid_price(
    invalid_price,
):
    engine, trade = (
        open_trade()
    )

    with pytest.raises(
        ValueError
    ):
        engine.update_price(
            trade_id=trade.trade_id,
            current_price=invalid_price,
        )


def test_update_missing_trade_rejected():
    engine = (
        PaperTradingEngine()
    )

    with pytest.raises(
        ValueError
    ):
        engine.update_price(
            trade_id="missing",
            current_price=100,
        )


# ---------------------------------
# AUTOMATIC STOP LOSS
# ---------------------------------


def test_stop_loss_automatically_closes_trade():
    engine, trade = (
        open_trade()
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=80,
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.STOP_LOSS
    )


def test_price_below_stop_loss_closes_trade():
    engine, trade = (
        open_trade()
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=75,
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_price
        == 75.0
    )


def test_stop_loss_realized_pnl_is_loss():
    engine, trade = (
        open_trade()
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=80,
    )

    assert (
        closed.realized_pnl
        == -1500.0
    )


# ---------------------------------
# AUTOMATIC TARGET
# ---------------------------------


def test_target_automatically_closes_trade():
    engine, trade = (
        open_trade()
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=140,
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.TARGET
    )


def test_price_above_target_closes_trade():
    engine, trade = (
        open_trade()
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=150,
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_price
        == 150.0
    )


def test_target_realized_pnl_is_profit():
    engine, trade = (
        open_trade()
    )

    closed = engine.update_price(
        trade_id=trade.trade_id,
        current_price=140,
    )

    assert (
        closed.realized_pnl
        == 3000.0
    )


# ---------------------------------
# AUTO CLOSE DISABLED
# ---------------------------------


def test_auto_close_false_does_not_close_at_stop_loss():
    engine, trade = (
        open_trade()
    )

    updated = engine.update_price(
        trade_id=trade.trade_id,
        current_price=70,
        auto_close=False,
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )


def test_auto_close_false_does_not_close_at_target():
    engine, trade = (
        open_trade()
    )

    updated = engine.update_price(
        trade_id=trade.trade_id,
        current_price=160,
        auto_close=False,
    )

    assert (
        updated.status
        == PaperTradeStatus.OPEN
    )


# ---------------------------------
# MANUAL CLOSE
# ---------------------------------


def test_manual_close_closes_trade():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=110,
    )

    assert (
        closed.status
        == PaperTradeStatus.CLOSED
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.MANUAL_EXIT
    )


def test_manual_close_calculates_realized_profit():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=110,
    )

    assert (
        closed.realized_pnl
        == 750.0
    )


def test_manual_close_calculates_realized_loss():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=90,
    )

    assert (
        closed.realized_pnl
        == -750.0
    )


def test_closed_trade_has_no_unrealized_pnl():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=110,
    )

    assert (
        closed.unrealized_pnl
        is None
    )


def test_closed_trade_records_exit_price():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=115,
    )

    assert (
        closed.exit_price
        == 115.0
    )


def test_closed_trade_records_timestamp():
    engine, trade = (
        open_trade()
    )

    timestamp = (
        "2026-07-12T11:00:00+00:00"
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=110,
        closed_at=timestamp,
    )

    assert (
        closed.closed_at
        == timestamp
    )

    assert (
        closed.updated_at
        == timestamp
    )


def test_cannot_close_trade_twice():
    engine, trade = (
        open_trade()
    )

    engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=110,
    )

    with pytest.raises(
        ValueError
    ):
        engine.close_trade(
            trade_id=trade.trade_id,
            exit_price=120,
        )


def test_cannot_update_closed_trade():
    engine, trade = (
        open_trade()
    )

    engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=110,
    )

    with pytest.raises(
        ValueError
    ):
        engine.update_price(
            trade_id=trade.trade_id,
            current_price=120,
        )


# ---------------------------------
# EXIT REASON VALIDATION
# ---------------------------------


def test_explicit_stop_loss_exit_reason_allowed():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=80,
        exit_reason=(
            PaperTradeExitReason.STOP_LOSS
        ),
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.STOP_LOSS
    )


def test_explicit_target_exit_reason_allowed():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=140,
        exit_reason=(
            PaperTradeExitReason.TARGET
        ),
    )

    assert (
        closed.exit_reason
        == PaperTradeExitReason.TARGET
    )


def test_invalid_exit_reason_rejected():
    engine, trade = (
        open_trade()
    )

    with pytest.raises(
        ValueError
    ):
        engine.close_trade(
            trade_id=trade.trade_id,
            exit_price=110,
            exit_reason="INVALID",
        )


# ---------------------------------
# COUNTS
# ---------------------------------


def test_trade_counts_track_lifecycle():
    engine = (
        PaperTradingEngine()
    )

    open_trade(
        engine=engine,
        trade_id="paper-001",
    )

    open_trade(
        engine=engine,
        trade_id="paper-002",
    )

    assert (
        engine.count_trades()
        == 2
    )

    assert (
        engine.count_open_trades()
        == 2
    )

    assert (
        engine.count_closed_trades()
        == 0
    )

    engine.close_trade(
        trade_id="paper-001",
        exit_price=110,
    )

    assert (
        engine.count_trades()
        == 2
    )

    assert (
        engine.count_open_trades()
        == 1
    )

    assert (
        engine.count_closed_trades()
        == 1
    )


# ---------------------------------
# DEFENSIVE COPY SAFETY
# ---------------------------------


def test_open_trade_result_cannot_mutate_engine_state():
    engine, trade = (
        open_trade()
    )

    trade.current_price = 999
    trade.metadata[
        "changed"
    ] = True

    stored = engine.get_trade(
        "paper-001"
    )

    assert (
        stored.current_price
        == 100.0
    )

    assert (
        "changed"
        not in stored.metadata
    )


def test_update_result_cannot_mutate_engine_state():
    engine, trade = (
        open_trade()
    )

    updated = engine.update_price(
        trade_id=trade.trade_id,
        current_price=110,
        auto_close=False,
    )

    updated.current_price = 999

    stored = engine.get_trade(
        trade.trade_id
    )

    assert (
        stored.current_price
        == 110.0
    )


def test_close_result_cannot_mutate_engine_state():
    engine, trade = (
        open_trade()
    )

    closed = engine.close_trade(
        trade_id=trade.trade_id,
        exit_price=110,
    )

    closed.realized_pnl = 999999

    stored = engine.get_trade(
        trade.trade_id
    )

    assert (
        stored.realized_pnl
        == 750.0
    )


# ---------------------------------
# INPUT IMMUTABILITY
# ---------------------------------


def test_pipeline_result_is_not_mutated():
    engine = (
        PaperTradingEngine()
    )

    result = (
        make_pipeline_result()
    )

    original = deepcopy(
        result
    )

    engine.open_trade(
        pipeline_result=result,
        underlying="NIFTY",
        exchange="NSE",
    )

    assert (
        result
        == original
    )


# ---------------------------------
# BEARISH PE TRADE
# ---------------------------------


def test_bearish_pe_trade_can_open():
    engine, trade = (
        open_trade(
            direction="BEARISH",
            option_type="PE",
        )
    )

    assert (
        trade.direction
        == "BEARISH"
    )

    assert (
        trade.option_type
        == "PE"
    )

    assert (
        trade.status
        == PaperTradeStatus.OPEN
    )