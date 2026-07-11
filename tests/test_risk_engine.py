import pytest
from services.risk_engine import (
    calculate_trade_risk,
)


def test_lot_based_risk_allows_valid_trade():

    result = calculate_trade_risk(
        capital=100000,
        entry_price=100,
        stop_loss_price=90,
        target_price=120,
        lot_size=50,
        risk_percent=1,
    )

    assert result["allowed"] is True
    assert (
        result["decision"]
        == "TRADE_ALLOWED"
    )
    assert result["lots"] == 2
    assert result["quantity"] == 100

    assert (
        result["estimated_maximum_loss"]
        == 1000
    )


def test_lot_based_risk_rejects_large_loss():

    result = calculate_trade_risk(
        capital=10000,
        entry_price=100,
        stop_loss_price=80,
        target_price=140,
        lot_size=50,
        risk_percent=1,
    )

    assert result["allowed"] is False
    assert result["lots"] == 0


def test_lot_based_risk_rejects_poor_reward():

    result = calculate_trade_risk(
        capital=100000,
        entry_price=100,
        stop_loss_price=90,
        target_price=110,
        lot_size=50,
        risk_percent=1,
        minimum_risk_reward=1.5,
    )

    assert result["allowed"] is False

    assert (
        result["risk_reward_ratio"]
        == 1.0
    )


def test_lot_based_capital_limit():

    result = calculate_trade_risk(
        capital=10000,
        entry_price=100,
        stop_loss_price=99,
        target_price=103,
        lot_size=50,
        risk_percent=10,
        maximum_capital_usage_percent=50,
    )

    assert result["allowed"] is True
    assert result["lots"] == 1
    assert result["quantity"] == 50

    assert (
        result["required_capital"]
        == 5000
    )


def test_lot_based_equal_entry_stop_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "Entry price and stop-loss price "
            "cannot be equal"
        ),
    ):
        calculate_trade_risk(
            capital=100000,
            entry_price=100,
            stop_loss_price=100,
            target_price=120,
            lot_size=50,
        )