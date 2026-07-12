"""
Tests for the paper trade validator.

The validator must fail closed and only permit
valid TRADE_ALLOWED pipeline results.
"""

from copy import deepcopy

import pytest

from services.paper_trade_validator import (
    PaperTradeValidator,
)


def make_valid_pipeline_result():
    return {
        "decision": "TRADE_ALLOWED",
        "direction": "BULLISH",
        "contract": {
            "selected": True,
            "symbol": "NIFTY30JUL24200CE",
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


def test_valid_pipeline_result_is_accepted():
    result = (
        PaperTradeValidator
        .validate_pipeline_result(
            make_valid_pipeline_result()
        )
    )

    assert (
        result["decision"]
        == "TRADE_ALLOWED"
    )

    assert (
        result["direction"]
        == "BULLISH"
    )

    assert (
        result["contract"]["option_type"]
        == "CE"
    )


def test_valid_bearish_pe_trade_is_accepted():
    data = make_valid_pipeline_result()

    data["direction"] = "BEARISH"
    data["contract"]["option_type"] = "PE"
    data["contract"]["symbol"] = (
        "NIFTY30JUL24200PE"
    )

    result = (
        PaperTradeValidator
        .validate_pipeline_result(
            data
        )
    )

    assert (
        result["direction"]
        == "BEARISH"
    )

    assert (
        result["contract"]["option_type"]
        == "PE"
    )


def test_no_trade_decision_is_rejected():
    data = make_valid_pipeline_result()

    data["decision"] = "NO_TRADE"

    with pytest.raises(
        ValueError,
        match="TRADE_ALLOWED",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_trade_rejected_decision_is_rejected():
    data = make_valid_pipeline_result()

    data["decision"] = "TRADE_REJECTED"

    with pytest.raises(
        ValueError,
        match="TRADE_ALLOWED",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_missing_decision_is_rejected():
    data = make_valid_pipeline_result()

    del data["decision"]

    with pytest.raises(
        ValueError,
        match="decision",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_invalid_direction_is_rejected():
    data = make_valid_pipeline_result()

    data["direction"] = "NEUTRAL"

    with pytest.raises(
        ValueError,
        match="BULLISH or BEARISH",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_unselected_contract_is_rejected():
    data = make_valid_pipeline_result()

    data["contract"]["selected"] = False

    with pytest.raises(
        ValueError,
        match="selected option contract",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_missing_contract_is_rejected():
    data = make_valid_pipeline_result()

    data["contract"] = None

    with pytest.raises(
        ValueError,
        match="contract must be a dictionary",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_invalid_option_type_is_rejected():
    data = make_valid_pipeline_result()

    data["contract"]["option_type"] = "XX"

    with pytest.raises(
        ValueError,
        match="CE or PE",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_bullish_pe_mismatch_is_rejected():
    data = make_valid_pipeline_result()

    data["contract"]["option_type"] = "PE"

    with pytest.raises(
        ValueError,
        match="BULLISH.*CE",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_bearish_ce_mismatch_is_rejected():
    data = make_valid_pipeline_result()

    data["direction"] = "BEARISH"

    with pytest.raises(
        ValueError,
        match="BEARISH.*PE",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        0,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
    ],
)
def test_invalid_contract_premium_is_rejected(
    value,
):
    data = make_valid_pipeline_result()

    data["contract"]["premium"] = value

    with pytest.raises(
        ValueError
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        1.5,
        "1.5",
        True,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_lot_size_is_rejected(
    value,
):
    data = make_valid_pipeline_result()

    data["contract"]["lot_size"] = value

    with pytest.raises(
        ValueError
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_integral_float_lot_size_is_accepted():
    data = make_valid_pipeline_result()

    data["contract"]["lot_size"] = 75.0

    result = (
        PaperTradeValidator
        .validate_pipeline_result(
            data
        )
    )

    assert (
        result["contract"]["lot_size"]
        == 75
    )


def test_numeric_string_lot_size_is_accepted():
    data = make_valid_pipeline_result()

    data["contract"]["lot_size"] = "75"

    result = (
        PaperTradeValidator
        .validate_pipeline_result(
            data
        )
    )

    assert (
        result["contract"]["lot_size"]
        == 75
    )


def test_trade_plan_not_allowed_is_rejected():
    data = make_valid_pipeline_result()

    data["trade_plan"]["allowed"] = False

    with pytest.raises(
        ValueError,
        match="trade_plan must explicitly allow",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_risk_not_allowed_is_rejected():
    data = make_valid_pipeline_result()

    data["trade_plan"]["risk"]["allowed"] = (
        False
    )

    with pytest.raises(
        ValueError,
        match="risk must explicitly allow",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_stop_loss_must_be_below_entry():
    data = make_valid_pipeline_result()

    data["trade_plan"]["levels"][
        "option_stop_loss"
    ] = 100

    with pytest.raises(
        ValueError,
        match="stop-loss price must be below",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_target_must_be_above_entry():
    data = make_valid_pipeline_result()

    data["trade_plan"]["levels"][
        "option_target"
    ] = 100

    with pytest.raises(
        ValueError,
        match="target price must be above",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_quantity_must_match_lot_size_times_lots():
    data = make_valid_pipeline_result()

    data["trade_plan"]["risk"][
        "quantity"
    ] = 100

    with pytest.raises(
        ValueError,
        match="quantity must equal",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_fractional_lots_are_rejected():
    data = make_valid_pipeline_result()

    data["trade_plan"]["risk"]["lots"] = 1.5

    with pytest.raises(
        ValueError
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_fractional_quantity_is_rejected():
    data = make_valid_pipeline_result()

    data["trade_plan"]["risk"][
        "quantity"
    ] = 75.5

    with pytest.raises(
        ValueError
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_material_premium_entry_mismatch_is_rejected():
    data = make_valid_pipeline_result()

    data["contract"]["premium"] = 150

    with pytest.raises(
        ValueError,
        match="materially inconsistent",
    ):
        (
            PaperTradeValidator
            .validate_pipeline_result(
                data
            )
        )


def test_small_premium_entry_difference_is_accepted():
    data = make_valid_pipeline_result()

    data["contract"]["premium"] = 103

    result = (
        PaperTradeValidator
        .validate_pipeline_result(
            data
        )
    )

    assert (
        result["contract"]["premium"]
        == 103
    )


def test_validate_open_request_normalizes_identity():
    result = (
        PaperTradeValidator
        .validate_open_request(
            pipeline_result=(
                make_valid_pipeline_result()
            ),
            underlying=" nifty ",
            exchange=" nse ",
            symboltoken=" 99926000 ",
        )
    )

    assert (
        result["underlying"]
        == "NIFTY"
    )

    assert (
        result["exchange"]
        == "NSE"
    )

    assert (
        result["symboltoken"]
        == "99926000"
    )


def test_empty_underlying_is_rejected():
    with pytest.raises(
        ValueError,
        match="underlying",
    ):
        (
            PaperTradeValidator
            .validate_open_request(
                pipeline_result=(
                    make_valid_pipeline_result()
                ),
                underlying="",
                exchange="NSE",
            )
        )


def test_empty_exchange_is_rejected():
    with pytest.raises(
        ValueError,
        match="exchange",
    ):
        (
            PaperTradeValidator
            .validate_open_request(
                pipeline_result=(
                    make_valid_pipeline_result()
                ),
                underlying="NIFTY",
                exchange="",
            )
        )


def test_validator_does_not_mutate_input():
    data = make_valid_pipeline_result()

    original = deepcopy(
        data
    )

    (
        PaperTradeValidator
        .validate_pipeline_result(
            data
        )
    )

    assert data == original


def test_returned_data_is_independent():
    data = make_valid_pipeline_result()

    result = (
        PaperTradeValidator
        .validate_pipeline_result(
            data
        )
    )

    result["contract"]["symbol"] = "CHANGED"

    assert (
        data["contract"]["symbol"]
        == "NIFTY30JUL24200CE"
    )