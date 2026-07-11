import pytest

from services.risk_engine import (
    evaluate_trade_risk,
)


def bullish_strategy():
    return {
        "strategy": "BREAKOUT",
        "direction": "BULLISH",
        "decision": "TRADE",
    }


def bearish_strategy():
    return {
        "strategy": "BREAKDOWN",
        "direction": "BEARISH",
        "decision": "TRADE",
    }


def test_approves_valid_bullish_trade():

    result = evaluate_trade_risk(
        strategy=bullish_strategy(),
        capital=100000,
        entry_price=100,
        stop_loss=95,
        target_price=110,
    )

    assert result["approved"] is True
    assert result["decision"] == "APPROVED"
    assert result["position_size"] == 200
    assert result["risk_reward_ratio"] == 2.0


def test_approves_valid_bearish_trade():

    result = evaluate_trade_risk(
        strategy=bearish_strategy(),
        capital=100000,
        entry_price=100,
        stop_loss=105,
        target_price=90,
    )

    assert result["approved"] is True
    assert result["risk_reward_ratio"] == 2.0


def test_rejects_bad_risk_reward():

    result = evaluate_trade_risk(
        strategy=bullish_strategy(),
        capital=100000,
        entry_price=100,
        stop_loss=95,
        target_price=103,
    )

    assert result["approved"] is False
    assert result["decision"] == "REJECTED"


def test_rejects_daily_loss_limit():

    result = evaluate_trade_risk(
        strategy=bullish_strategy(),
        capital=100000,
        entry_price=100,
        stop_loss=95,
        target_price=110,
        daily_pnl=-3000,
    )

    assert result["approved"] is False

    assert (
        "Maximum daily loss limit reached."
        in result["reasons"]
    )


def test_rejects_consecutive_losses():

    result = evaluate_trade_risk(
        strategy=bullish_strategy(),
        capital=100000,
        entry_price=100,
        stop_loss=95,
        target_price=110,
        consecutive_losses=3,
    )

    assert result["approved"] is False


def test_kill_switch_rejects_trade():

    result = evaluate_trade_risk(
        strategy=bullish_strategy(),
        capital=100000,
        entry_price=100,
        stop_loss=95,
        target_price=110,
        kill_switch=True,
    )

    assert result["approved"] is False

    assert (
        "Emergency kill switch is active."
        in result["reasons"]
    )


def test_strategy_no_trade_is_rejected():

    strategy = {
        "direction": "BULLISH",
        "decision": "NO_TRADE",
    }

    result = evaluate_trade_risk(
        strategy=strategy,
        capital=100000,
        entry_price=100,
        stop_loss=95,
        target_price=110,
    )

    assert result["approved"] is False


def test_invalid_capital():

    with pytest.raises(
        ValueError,
        match="Capital must be greater than zero",
    ):
        evaluate_trade_risk(
            strategy=bullish_strategy(),
            capital=0,
            entry_price=100,
            stop_loss=95,
            target_price=110,
        )