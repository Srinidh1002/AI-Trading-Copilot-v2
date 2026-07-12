"""
Tests for the paper trading P&L engine.
"""

from types import SimpleNamespace

import pytest

from services.paper_pnl_engine import (
    PaperPnLEngine,
)


def test_calculate_profit():
    assert (
        PaperPnLEngine.calculate_pnl(
            entry_price=100,
            current_price=120,
            quantity=75,
        )
        == 1500
    )


def test_calculate_loss():
    assert (
        PaperPnLEngine.calculate_pnl(
            entry_price=100,
            current_price=80,
            quantity=75,
        )
        == -1500
    )


def test_calculate_break_even():
    assert (
        PaperPnLEngine.calculate_pnl(
            entry_price=100,
            current_price=100,
            quantity=75,
        )
        == 0
    )


def test_positive_pnl_percent():
    assert (
        PaperPnLEngine.calculate_pnl_percent(
            entry_price=100,
            current_price=140,
        )
        == 40
    )


def test_negative_pnl_percent():
    assert (
        PaperPnLEngine.calculate_pnl_percent(
            entry_price=100,
            current_price=80,
        )
        == -20
    )


def test_position_value():
    assert (
        PaperPnLEngine.calculate_position_value(
            price=100,
            quantity=75,
        )
        == 7500
    )


def test_unrealized_snapshot():
    result = (
        PaperPnLEngine.calculate_unrealized(
            entry_price=100,
            current_price=120,
            quantity=75,
        )
    )

    assert result == {
        "type": "UNREALIZED",
        "entry_price": 100.0,
        "current_price": 120.0,
        "quantity": 75,
        "entry_value": 7500.0,
        "current_value": 9000.0,
        "pnl": 1500.0,
        "pnl_percent": 20.0,
    }


def test_realized_snapshot():
    result = (
        PaperPnLEngine.calculate_realized(
            entry_price=100,
            exit_price=140,
            quantity=75,
        )
    )

    assert result == {
        "type": "REALIZED",
        "entry_price": 100.0,
        "exit_price": 140.0,
        "quantity": 75,
        "entry_value": 7500.0,
        "exit_value": 10500.0,
        "pnl": 3000.0,
        "pnl_percent": 40.0,
    }


def test_open_trade_snapshot():
    trade = SimpleNamespace(
        status="OPEN",
        entry_price=100,
        current_price=120,
        quantity=75,
    )

    result = (
        PaperPnLEngine
        .calculate_trade_snapshot(
            trade
        )
    )

    assert result["type"] == "UNREALIZED"
    assert result["pnl"] == 1500


def test_open_trade_snapshot_price_override():
    trade = SimpleNamespace(
        status="OPEN",
        entry_price=100,
        current_price=110,
        quantity=75,
    )

    result = (
        PaperPnLEngine
        .calculate_trade_snapshot(
            trade,
            current_price=130,
        )
    )

    assert result["current_price"] == 130
    assert result["pnl"] == 2250


def test_closed_trade_snapshot():
    trade = SimpleNamespace(
        status="CLOSED",
        entry_price=100,
        exit_price=80,
        quantity=75,
    )

    result = (
        PaperPnLEngine
        .calculate_trade_snapshot(
            trade
        )
    )

    assert result["type"] == "REALIZED"
    assert result["pnl"] == -1500


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        -1,
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_entry_price_rejected(
    value,
):
    with pytest.raises(
        ValueError
    ):
        (
            PaperPnLEngine.calculate_pnl(
                entry_price=value,
                current_price=100,
                quantity=75,
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        -1,
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_current_price_rejected(
    value,
):
    with pytest.raises(
        ValueError
    ):
        (
            PaperPnLEngine.calculate_pnl(
                entry_price=100,
                current_price=value,
                quantity=75,
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        -1,
        1.5,
        "1.5",
        True,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_quantity_rejected(
    value,
):
    with pytest.raises(
        ValueError
    ):
        (
            PaperPnLEngine.calculate_pnl(
                entry_price=100,
                current_price=120,
                quantity=value,
            )
        )


def test_integral_float_quantity_accepted():
    result = (
        PaperPnLEngine.calculate_pnl(
            entry_price=100,
            current_price=120,
            quantity=75.0,
        )
    )

    assert result == 1500


def test_numeric_string_quantity_accepted():
    result = (
        PaperPnLEngine.calculate_pnl(
            entry_price=100,
            current_price=120,
            quantity="75",
        )
    )

    assert result == 1500


def test_missing_trade_rejected():
    with pytest.raises(
        ValueError,
        match="trade is required",
    ):
        (
            PaperPnLEngine
            .calculate_trade_snapshot(
                None
            )
        )


def test_invalid_trade_status_rejected():
    trade = SimpleNamespace(
        status="UNKNOWN",
        entry_price=100,
        current_price=120,
        quantity=75,
    )

    with pytest.raises(
        ValueError,
        match="OPEN or CLOSED",
    ):
        (
            PaperPnLEngine
            .calculate_trade_snapshot(
                trade
            )
        )


def test_open_trade_without_current_price_rejected():
    trade = SimpleNamespace(
        status="OPEN",
        entry_price=100,
        current_price=None,
        quantity=75,
    )

    with pytest.raises(
        ValueError
    ):
        (
            PaperPnLEngine
            .calculate_trade_snapshot(
                trade
            )
        )


def test_closed_trade_without_exit_price_rejected():
    trade = SimpleNamespace(
        status="CLOSED",
        entry_price=100,
        exit_price=None,
        quantity=75,
    )

    with pytest.raises(
        ValueError
    ):
        (
            PaperPnLEngine
            .calculate_trade_snapshot(
                trade
            )
        )


def test_decimal_result_is_rounded():
    result = (
        PaperPnLEngine.calculate_pnl(
            entry_price=100.123,
            current_price=101.456,
            quantity=75,
        )
    )

    assert result == 99.98


def test_percentage_result_is_rounded():
    result = (
        PaperPnLEngine
        .calculate_pnl_percent(
            entry_price=99,
            current_price=100,
        )
    )

    assert result == 1.01