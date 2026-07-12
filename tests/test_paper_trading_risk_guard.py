from datetime import datetime, timezone

import pytest

from services.paper_trading_risk_guard import (
    PaperTradingRiskGuard,
)


NOW = datetime(
    2026,
    7,
    12,
    10,
    0,
    tzinfo=timezone.utc,
)


def make_trade(
    *,
    trade_id="trade-1",
    status="OPEN",
    underlying="NIFTY",
    option_symbol="NIFTY_TEST_CE",
    symboltoken="123",
    opened_at="2026-07-12T09:00:00+00:00",
    closed_at=None,
    realized_pnl=None,
):
    return {
        "trade_id": trade_id,
        "status": status,
        "underlying": underlying,
        "option_symbol": option_symbol,
        "symboltoken": symboltoken,
        "opened_at": opened_at,
        "closed_at": closed_at,
        "realized_pnl": realized_pnl,
    }


def make_candidate(
    *,
    underlying="NIFTY",
    option_symbol="NIFTY_NEW_CE",
    symboltoken="999",
):
    return {
        "underlying": underlying,
        "option_symbol": option_symbol,
        "symboltoken": symboltoken,
    }


def make_guard(
    **kwargs,
):
    defaults = {
        "max_open_positions": 2,
        "max_trades_per_day": 5,
        "max_daily_realized_loss": 500.0,
        "block_duplicate_positions": True,
        "kill_switch": False,
        "now_function": lambda: NOW,
    }

    defaults.update(
        kwargs
    )

    return PaperTradingRiskGuard(
        **defaults
    )


# ============================================================
# INITIALIZATION
# ============================================================


def test_default_initialization():

    guard = (
        PaperTradingRiskGuard()
    )

    assert (
        guard.max_open_positions
        == 1
    )

    assert (
        guard.max_trades_per_day
        == 5
    )

    assert (
        guard.max_daily_realized_loss
        == 500.0
    )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        1.5,
        "2",
        True,
        None,
    ],
)
def test_invalid_max_open_positions(
    value,
):
    with pytest.raises(
        ValueError
    ):
        PaperTradingRiskGuard(
            max_open_positions=value
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        1.5,
        "5",
        True,
        None,
    ],
)
def test_invalid_max_trades_per_day(
    value,
):
    with pytest.raises(
        ValueError
    ):
        PaperTradingRiskGuard(
            max_trades_per_day=value
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        True,
        None,
        "abc",
        float("inf"),
        float("nan"),
    ],
)
def test_invalid_max_daily_loss(
    value,
):
    with pytest.raises(
        ValueError
    ):
        PaperTradingRiskGuard(
            max_daily_realized_loss=value
        )


def test_numeric_string_daily_loss_allowed():

    guard = (
        PaperTradingRiskGuard(
            max_daily_realized_loss="500"
        )
    )

    assert (
        guard.max_daily_realized_loss
        == 500.0
    )


def test_invalid_duplicate_flag():

    with pytest.raises(
        ValueError
    ):
        PaperTradingRiskGuard(
            block_duplicate_positions=1
        )


def test_invalid_kill_switch():

    with pytest.raises(
        ValueError
    ):
        PaperTradingRiskGuard(
            kill_switch=1
        )


def test_invalid_now_function():

    with pytest.raises(
        ValueError
    ):
        PaperTradingRiskGuard(
            now_function="invalid"
        )


# ============================================================
# OPEN POSITION COUNT
# ============================================================


def test_counts_open_positions():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            trade_id="1",
            status="OPEN",
        ),
        make_trade(
            trade_id="2",
            status="CLOSED",
        ),
        make_trade(
            trade_id="3",
            status="open",
        ),
    ]

    assert (
        guard.count_open_positions(
            trades
        )
        == 2
    )


# ============================================================
# DAILY TRADE COUNT
# ============================================================


def test_counts_trades_opened_today():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            trade_id="1",
            opened_at=(
                "2026-07-12T08:00:00+00:00"
            ),
        ),
        make_trade(
            trade_id="2",
            opened_at=(
                "2026-07-12T09:00:00+00:00"
            ),
        ),
        make_trade(
            trade_id="3",
            opened_at=(
                "2026-07-11T09:00:00+00:00"
            ),
        ),
    ]

    assert (
        guard.count_trades_opened_today(
            trades,
            now=NOW,
        )
        == 2
    )


def test_invalid_opened_at_is_ignored():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            opened_at="invalid"
        )
    ]

    assert (
        guard.count_trades_opened_today(
            trades,
            now=NOW,
        )
        == 0
    )


# ============================================================
# DAILY REALIZED PNL
# ============================================================


def test_daily_realized_pnl():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            trade_id="1",
            status="CLOSED",
            closed_at=(
                "2026-07-12T08:00:00+00:00"
            ),
            realized_pnl=200,
        ),
        make_trade(
            trade_id="2",
            status="CLOSED",
            closed_at=(
                "2026-07-12T09:00:00+00:00"
            ),
            realized_pnl=-100,
        ),
        make_trade(
            trade_id="3",
            status="CLOSED",
            closed_at=(
                "2026-07-11T09:00:00+00:00"
            ),
            realized_pnl=-1000,
        ),
    ]

    assert (
        guard.get_daily_realized_pnl(
            trades,
            now=NOW,
        )
        == 100.0
    )


def test_open_trade_not_counted_in_realized_pnl():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            status="OPEN",
            closed_at=(
                "2026-07-12T09:00:00+00:00"
            ),
            realized_pnl=-1000,
        )
    ]

    assert (
        guard.get_daily_realized_pnl(
            trades,
            now=NOW,
        )
        == 0.0
    )


def test_invalid_realized_pnl_raises():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            status="CLOSED",
            closed_at=(
                "2026-07-12T09:00:00+00:00"
            ),
            realized_pnl="invalid",
        )
    ]

    with pytest.raises(
        ValueError
    ):
        guard.get_daily_realized_pnl(
            trades,
            now=NOW,
        )


# ============================================================
# KILL SWITCH
# ============================================================


def test_kill_switch_blocks_trade():

    guard = (
        make_guard(
            kill_switch=True
        )
    )

    result = (
        guard.evaluate(
            make_candidate(),
            [],
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "KILL_SWITCH_ACTIVE"
    )


def test_enable_kill_switch():

    guard = (
        make_guard()
    )

    guard.enable_kill_switch()

    assert (
        guard.kill_switch
        is True
    )


def test_disable_kill_switch():

    guard = (
        make_guard(
            kill_switch=True
        )
    )

    guard.disable_kill_switch()

    assert (
        guard.kill_switch
        is False
    )


# ============================================================
# OPEN POSITION LIMIT
# ============================================================


def test_max_open_positions_blocks():

    guard = (
        make_guard(
            max_open_positions=1
        )
    )

    trades = [
        make_trade(
            underlying="BANKNIFTY",
            option_symbol="BANK_TEST",
            symboltoken="111",
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "MAX_OPEN_POSITIONS_REACHED"
    )


# ============================================================
# DAILY TRADE LIMIT
# ============================================================


def test_daily_trade_limit_blocks():

    guard = (
        make_guard(
            max_trades_per_day=2
        )
    )

    trades = [
        make_trade(
            trade_id="1",
            status="CLOSED",
            underlying="BANKNIFTY",
            option_symbol="A",
            symboltoken="1",
            opened_at=(
                "2026-07-12T08:00:00+00:00"
            ),
            closed_at=(
                "2026-07-12T08:30:00+00:00"
            ),
            realized_pnl=10,
        ),
        make_trade(
            trade_id="2",
            status="CLOSED",
            underlying="SENSEX",
            option_symbol="B",
            symboltoken="2",
            opened_at=(
                "2026-07-12T09:00:00+00:00"
            ),
            closed_at=(
                "2026-07-12T09:30:00+00:00"
            ),
            realized_pnl=10,
        ),
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "code"
        ]
        == "MAX_DAILY_TRADES_REACHED"
    )


# ============================================================
# DAILY LOSS LIMIT
# ============================================================


def test_daily_loss_limit_blocks():

    guard = (
        make_guard(
            max_daily_realized_loss=500
        )
    )

    trades = [
        make_trade(
            status="CLOSED",
            underlying="BANKNIFTY",
            option_symbol="OLD",
            symboltoken="1",
            closed_at=(
                "2026-07-12T09:00:00+00:00"
            ),
            realized_pnl=-500,
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "MAX_DAILY_LOSS_REACHED"
    )


def test_profit_does_not_trigger_loss_limit():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            status="CLOSED",
            underlying="BANKNIFTY",
            option_symbol="OLD",
            symboltoken="1",
            closed_at=(
                "2026-07-12T09:00:00+00:00"
            ),
            realized_pnl=1000,
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "allowed"
        ]
        is True
    )


# ============================================================
# DUPLICATES
# ============================================================


def test_duplicate_symboltoken_blocks():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            underlying="BANKNIFTY",
            option_symbol="OTHER",
            symboltoken="999",
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(
                underlying="NIFTY",
                option_symbol="NEW",
                symboltoken="999",
            ),
            trades,
        )
    )

    assert (
        result[
            "code"
        ]
        == "DUPLICATE_OPEN_POSITION"
    )


def test_duplicate_option_symbol_blocks():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            underlying="BANKNIFTY",
            option_symbol="NIFTY_NEW_CE",
            symboltoken="111",
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "code"
        ]
        == "DUPLICATE_OPEN_POSITION"
    )


def test_duplicate_underlying_blocks():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            underlying="NIFTY",
            option_symbol="DIFFERENT",
            symboltoken="111",
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "code"
        ]
        == "DUPLICATE_OPEN_POSITION"
    )


def test_closed_trade_is_not_duplicate():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            status="CLOSED",
            closed_at=(
                "2026-07-11T09:00:00+00:00"
            ),
            realized_pnl=0,
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "allowed"
        ]
        is True
    )


def test_duplicate_blocking_can_be_disabled():

    guard = (
        make_guard(
            block_duplicate_positions=False
        )
    )

    trades = [
        make_trade()
    ]

    result = (
        guard.evaluate(
            make_candidate(
                underlying="NIFTY"
            ),
            trades,
        )
    )

    assert (
        result[
            "allowed"
        ]
        is True
    )


# ============================================================
# ALLOWED
# ============================================================


def test_clean_candidate_allowed():

    guard = (
        make_guard()
    )

    result = (
        guard.evaluate(
            make_candidate(),
            [],
        )
    )

    assert (
        result[
            "allowed"
        ]
        is True
    )

    assert (
        result[
            "code"
        ]
        == "ALLOWED"
    )


def test_is_allowed_returns_boolean():

    guard = (
        make_guard()
    )

    assert (
        guard.is_allowed(
            make_candidate(),
            [],
        )
        is True
    )


def test_metrics_are_returned():

    guard = (
        make_guard()
    )

    result = (
        guard.evaluate(
            make_candidate(),
            [],
        )
    )

    assert (
        result[
            "metrics"
        ][
            "open_positions"
        ]
        == 0
    )

    assert (
        result[
            "metrics"
        ][
            "trades_today"
        ]
        == 0
    )


# ============================================================
# FAIL CLOSED
# ============================================================


def test_missing_candidate_blocks():

    guard = (
        make_guard()
    )

    result = (
        guard.evaluate(
            None,
            [],
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "INVALID_CANDIDATE"
    )


def test_missing_trade_history_blocks():

    guard = (
        make_guard()
    )

    result = (
        guard.evaluate(
            make_candidate(),
            None,
        )
    )

    assert (
        result[
            "code"
        ]
        == "INVALID_TRADE_HISTORY"
    )


def test_non_iterable_trade_history_blocks():

    guard = (
        make_guard()
    )

    result = (
        guard.evaluate(
            make_candidate(),
            123,
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "INVALID_TRADE_HISTORY"
    )


def test_bad_realized_pnl_fails_closed():

    guard = (
        make_guard()
    )

    trades = [
        make_trade(
            status="CLOSED",
            closed_at=(
                "2026-07-12T09:00:00+00:00"
            ),
            realized_pnl="bad",
        )
    ]

    result = (
        guard.evaluate(
            make_candidate(),
            trades,
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "RISK_GUARD_ERROR"
    )


def test_invalid_now_fails_closed():

    guard = (
        make_guard()
    )

    result = (
        guard.evaluate(
            make_candidate(),
            [],
            now="invalid",
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "INVALID_CURRENT_TIME"
    )


def test_invalid_now_function_fails_closed():

    guard = (
        make_guard(
            now_function=lambda: "invalid"
        )
    )

    result = (
        guard.evaluate(
            make_candidate(),
            [],
        )
    )

    assert (
        result[
            "allowed"
        ]
        is False
    )

    assert (
        result[
            "code"
        ]
        == "RISK_GUARD_ERROR"
    )