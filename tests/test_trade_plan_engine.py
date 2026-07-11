import pytest

from services.trade_plan_engine import (
    build_trade_plan,
)


def bullish_contract():

    return {
        "selected": True,
        "decision": "CONTRACT_SELECTED",
        "symbol": "NIFTY14JUL2624200CE",
        "strike": 24200,
        "option_type": "CE",
        "expiry": "14JUL2026",
        "premium": 100,
        "score": 12,
        "reasons": [],
    }


def bearish_contract():

    return {
        "selected": True,
        "decision": "CONTRACT_SELECTED",
        "symbol": "NIFTY14JUL2624200PE",
        "strike": 24200,
        "option_type": "PE",
        "expiry": "14JUL2026",
        "premium": 100,
        "score": 12,
        "reasons": [],
    }


def test_builds_valid_bullish_trade_plan():

    result = build_trade_plan(
        contract=bullish_contract(),
        direction="BULLISH",
        spot_price=24200,
        atr=20,
        capital=100000,
        lot_size=50,
        risk_percent=1,
        option_stop_percent=20,
        minimum_risk_reward=2,
    )

    assert result["allowed"] is True

    assert (
        result["decision"]
        == "TRADE_ALLOWED"
    )

    assert (
        result["option_type"]
        == "CE"
    )

    assert (
        result["entry_price"]
        == 100
    )

    assert (
        result["stop_loss_price"]
        == 80
    )

    assert (
        result["target_price"]
        == 140
    )

    assert result["lots"] == 1
    assert result["quantity"] == 50


def test_builds_valid_bearish_trade_plan():

    result = build_trade_plan(
        contract=bearish_contract(),
        direction="BEARISH",
        spot_price=24200,
        atr=20,
        capital=100000,
        lot_size=50,
        risk_percent=1,
    )

    assert result["allowed"] is True

    assert (
        result["option_type"]
        == "PE"
    )


def test_rejects_unselected_contract():

    contract = bullish_contract()

    contract["selected"] = False

    result = build_trade_plan(
        contract=contract,
        direction="BULLISH",
        spot_price=24200,
        atr=20,
        capital=100000,
        lot_size=50,
    )

    assert result["allowed"] is False

    assert (
        result["decision"]
        == "TRADE_REJECTED"
    )

    assert result["levels"] is None
    assert result["risk"] is None


def test_rejects_direction_contract_mismatch():

    result = build_trade_plan(
        contract=bearish_contract(),
        direction="BULLISH",
        spot_price=24200,
        atr=20,
        capital=100000,
        lot_size=50,
    )

    assert result["allowed"] is False

    assert (
        "does not match"
        in result["reasons"][0]
    )


def test_rejects_when_risk_budget_cannot_buy_one_lot():

    result = build_trade_plan(
        contract=bullish_contract(),
        direction="BULLISH",
        spot_price=24200,
        atr=20,
        capital=10000,
        lot_size=50,
        risk_percent=1,
        option_stop_percent=20,
    )

    assert result["allowed"] is False

    assert result["lots"] == 0
    assert result["quantity"] == 0


def test_rejects_invalid_premium():

    contract = bullish_contract()

    contract["premium"] = 0

    with pytest.raises(
        ValueError,
        match=(
            "Selected contract premium must be "
            "greater than zero"
        ),
    ):
        build_trade_plan(
            contract=contract,
            direction="BULLISH",
            spot_price=24200,
            atr=20,
            capital=100000,
            lot_size=50,
        )
def test_uses_contract_lot_size_automatically():

    contract = {
        "selected": True,
        "symbol": "NIFTY14JUL24200CE",
        "strike": 24200,
        "option_type": "CE",
        "expiry": "14JUL2026",
        "premium": 100,
        "lot_size": 65,
    }

    result = build_trade_plan(
        contract=contract,
        direction="BULLISH",
        spot_price=24200,
        atr=100,
        capital=100000,
    )

    assert result["lot_size"] == 65
    assert result["lot_size_source"] == "CONTRACT"


def test_contract_lot_size_overrides_manual_fallback():

    contract = {
        "selected": True,
        "symbol": "NIFTY14JUL24200CE",
        "strike": 24200,
        "option_type": "CE",
        "expiry": "14JUL2026",
        "premium": 100,
        "lot_size": 65,
    }

    result = build_trade_plan(
        contract=contract,
        direction="BULLISH",
        spot_price=24200,
        atr=100,
        capital=100000,
        lot_size=50,
    )

    assert result["lot_size"] == 65
    assert result["lot_size_source"] == "CONTRACT"        