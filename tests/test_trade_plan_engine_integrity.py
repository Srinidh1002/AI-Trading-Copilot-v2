"""
Integrity and safety tests for the trade-plan engine.

Verifies:
- Missing and unselected contracts are rejected.
- Direction must match CE/PE contract type.
- Premium and lot size must be valid.
- Contract lot size has priority.
- Manual lot size works only as fallback.
- Trade levels and risk engine receive correct inputs.
- Final authorization follows the risk engine.
- Output preserves critical trade-plan data.

Read-only.
No orders are placed.
"""

from unittest.mock import patch

import pytest

from services.trade_plan_engine import (
    _normalize_lot_size,
    build_trade_plan,
)


def make_contract(
    selected=True,
    symbol="NIFTY14JUL2624200CE",
    option_type="CE",
    strike=24200,
    expiry="14JUL2026",
    premium=150.0,
    lot_size=75,
):
    return {
        "selected": selected,
        "symbol": symbol,
        "option_type": option_type,
        "strike": strike,
        "expiry": expiry,
        "premium": premium,
        "lot_size": lot_size,
    }


def make_levels():
    return {
        "option_entry_price": 150.0,
        "option_stop_loss": 140.0,
        "option_target": 170.0,
        "reasons": [
            "Dynamic trade levels calculated."
        ],
    }


def make_risk(
    allowed=True,
):
    return {
        "allowed": allowed,
        "lots": 1 if allowed else 0,
        "quantity": 75 if allowed else 0,
        "required_capital": (
            11250.0
            if allowed
            else 0.0
        ),
        "estimated_maximum_loss": (
            750.0
            if allowed
            else 0.0
        ),
        "risk_reward_ratio": 2.0,
        "reasons": [
            (
                "Risk authorization passed."
                if allowed
                else "Risk authorization failed."
            )
        ],
    }


def test_normalize_valid_integer_lot_size():

    assert (
        _normalize_lot_size(75)
        == 75
    )


def test_normalize_string_lot_size():

    assert (
        _normalize_lot_size("75.0")
        == 75
    )


def test_normalize_invalid_lot_size_returns_zero():

    assert (
        _normalize_lot_size("INVALID")
        == 0
    )


def test_normalize_zero_lot_size_returns_zero():

    assert (
        _normalize_lot_size(0)
        == 0
    )


def test_normalize_negative_lot_size_returns_zero():

    assert (
        _normalize_lot_size(-75)
        == 0
    )


def test_missing_contract_is_rejected():

    result = build_trade_plan(
        contract=None,
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=10000,
    )

    assert result["allowed"] is False
    assert result["decision"] == "TRADE_REJECTED"
    assert result["levels"] is None
    assert result["risk"] is None


def test_unselected_contract_is_rejected():

    result = build_trade_plan(
        contract=make_contract(
            selected=False,
        ),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=10000,
    )

    assert result["allowed"] is False
    assert result["decision"] == "TRADE_REJECTED"
    assert result["levels"] is None
    assert result["risk"] is None


def test_invalid_direction_is_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "direction must be "
            "BULLISH or BEARISH"
        ),
    ):
        build_trade_plan(
            contract=make_contract(),
            direction="NEUTRAL",
            spot_price=24206,
            atr=100,
            capital=10000,
        )


def test_bullish_direction_rejects_pe():

    result = build_trade_plan(
        contract=make_contract(
            symbol="NIFTY14JUL2624200PE",
            option_type="PE",
        ),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=10000,
    )

    assert result["allowed"] is False
    assert result["decision"] == "TRADE_REJECTED"
    assert result["levels"] is None
    assert result["risk"] is None


def test_bearish_direction_rejects_ce():

    result = build_trade_plan(
        contract=make_contract(
            option_type="CE",
        ),
        direction="BEARISH",
        spot_price=24206,
        atr=100,
        capital=10000,
    )

    assert result["allowed"] is False
    assert result["decision"] == "TRADE_REJECTED"


def test_zero_premium_is_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "premium must be "
            "greater than zero"
        ),
    ):
        build_trade_plan(
            contract=make_contract(
                premium=0,
            ),
            direction="BULLISH",
            spot_price=24206,
            atr=100,
            capital=10000,
        )


def test_negative_premium_is_rejected():

    with pytest.raises(
        ValueError,
        match=(
            "premium must be "
            "greater than zero"
        ),
    ):
        build_trade_plan(
            contract=make_contract(
                premium=-10,
            ),
            direction="BULLISH",
            spot_price=24206,
            atr=100,
            capital=10000,
        )


def test_missing_lot_size_is_rejected():

    with pytest.raises(
        ValueError,
        match="No valid lot size",
    ):
        build_trade_plan(
            contract=make_contract(
                lot_size=0,
            ),
            direction="BULLISH",
            spot_price=24206,
            atr=100,
            capital=10000,
            lot_size=None,
        )


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_contract_lot_size_has_priority(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk(
            allowed=True
        )
    )

    result = build_trade_plan(
        contract=make_contract(
            lot_size=75,
        ),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=20000,
        lot_size=50,
    )

    assert result["lot_size"] == 75

    assert (
        result["lot_size_source"]
        == "CONTRACT"
    )

    assert (
        mock_risk.call_args.kwargs[
            "lot_size"
        ]
        == 75
    )


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_manual_lot_size_used_as_fallback(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk(
            allowed=True
        )
    )

    result = build_trade_plan(
        contract=make_contract(
            lot_size=0,
        ),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=20000,
        lot_size=50,
    )

    assert result["lot_size"] == 50

    assert (
        result["lot_size_source"]
        == "MANUAL_FALLBACK"
    )

    assert (
        mock_risk.call_args.kwargs[
            "lot_size"
        ]
        == 50
    )


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_bullish_trade_can_be_allowed(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk(
            allowed=True
        )
    )

    result = build_trade_plan(
        contract=make_contract(),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=20000,
    )

    assert result["allowed"] is True

    assert (
        result["decision"]
        == "TRADE_ALLOWED"
    )

    assert result["direction"] == "BULLISH"
    assert result["option_type"] == "CE"


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_bearish_trade_can_be_allowed(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk(
            allowed=True
        )
    )

    contract = make_contract(
        symbol="NIFTY14JUL2624200PE",
        option_type="PE",
    )

    result = build_trade_plan(
        contract=contract,
        direction="BEARISH",
        spot_price=24206,
        atr=100,
        capital=20000,
    )

    assert result["allowed"] is True

    assert (
        result["decision"]
        == "TRADE_ALLOWED"
    )

    assert result["direction"] == "BEARISH"
    assert result["option_type"] == "PE"


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_failed_risk_authorization_rejects_trade(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk(
            allowed=False
        )
    )

    result = build_trade_plan(
        contract=make_contract(),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=10000,
    )

    assert result["allowed"] is False

    assert (
        result["decision"]
        == "TRADE_REJECTED"
    )


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_trade_levels_receive_market_inputs(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk()
    )

    build_trade_plan(
        contract=make_contract(),
        direction="BULLISH",
        spot_price=24206,
        atr=125,
        capital=20000,
        support=24100,
        resistance=24300,
        minimum_risk_reward=2.5,
        option_stop_percent=15,
        atr_stop_multiplier=1.5,
    )

    kwargs = (
        mock_levels.call_args.kwargs
    )

    assert kwargs["direction"] == "BULLISH"
    assert kwargs["spot_price"] == 24206
    assert kwargs["atr"] == 125
    assert kwargs["option_premium"] == 150.0
    assert kwargs["support"] == 24100
    assert kwargs["resistance"] == 24300

    assert (
        kwargs["minimum_risk_reward"]
        == 2.5
    )

    assert (
        kwargs["option_stop_percent"]
        == 15
    )

    assert (
        kwargs["atr_stop_multiplier"]
        == 1.5
    )


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_risk_engine_receives_calculated_levels(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk()
    )

    build_trade_plan(
        contract=make_contract(),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=50000,
        risk_percent=2.0,
        minimum_risk_reward=2.5,
        maximum_capital_usage_percent=50.0,
    )

    kwargs = (
        mock_risk.call_args.kwargs
    )

    assert kwargs["capital"] == 50000
    assert kwargs["entry_price"] == 150.0
    assert kwargs["stop_loss_price"] == 140.0
    assert kwargs["target_price"] == 170.0
    assert kwargs["lot_size"] == 75
    assert kwargs["risk_percent"] == 2.0

    assert (
        kwargs["minimum_risk_reward"]
        == 2.5
    )

    assert (
        kwargs[
            "maximum_capital_usage_percent"
        ]
        == 50.0
    )


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_final_plan_preserves_trade_details(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk(
            allowed=True
        )
    )

    result = build_trade_plan(
        contract=make_contract(),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=20000,
    )

    assert (
        result["symbol"]
        == "NIFTY14JUL2624200CE"
    )

    assert result["strike"] == 24200
    assert result["expiry"] == "14JUL2026"
    assert result["entry_price"] == 150.0
    assert result["stop_loss_price"] == 140.0
    assert result["target_price"] == 170.0
    assert result["lot_size"] == 75
    assert result["lots"] == 1
    assert result["quantity"] == 75

    assert (
        result["required_capital"]
        == 11250.0
    )

    assert (
        result["estimated_maximum_loss"]
        == 750.0
    )

    assert (
        result["risk_reward_ratio"]
        == 2.0
    )


@patch(
    "services.trade_plan_engine."
    "calculate_trade_risk"
)
@patch(
    "services.trade_plan_engine."
    "calculate_trade_levels"
)
def test_final_plan_combines_reasons(
    mock_levels,
    mock_risk,
):

    mock_levels.return_value = (
        make_levels()
    )

    mock_risk.return_value = (
        make_risk(
            allowed=True
        )
    )

    result = build_trade_plan(
        contract=make_contract(),
        direction="BULLISH",
        spot_price=24206,
        atr=100,
        capital=20000,
    )

    reasons = result["reasons"]

    assert (
        "Dynamic trade levels calculated."
        in reasons
    )

    assert (
        "Risk authorization passed."
        in reasons
    )

    assert any(
        "exchange contract"
        in reason
        for reason in reasons
    )