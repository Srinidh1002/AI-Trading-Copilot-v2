import pytest

from services.options_risk_engine import (
    evaluate_options_risk,
)


def valid_option():
    return {
        "capital": 100000,
        "premium": 100,
        "lot_size": 25,
        "bid_price": 99.5,
        "ask_price": 100.5,
        "volume": 5000,
        "open_interest": 10000,
        "iv": 25,
        "delta": 0.55,
        "theta": -5,
        "days_to_expiry": 5,
    }


def test_approves_liquid_option():

    result = evaluate_options_risk(
        **valid_option()
    )

    assert result["approved"] is True
    assert result["decision"] == "APPROVED"
    assert result["lots"] == 4
    assert result["quantity"] == 100
    assert result["premium_exposure"] == 10000


def test_rejects_wide_spread():

    data = valid_option()

    data["bid_price"] = 90
    data["ask_price"] = 110

    result = evaluate_options_risk(**data)

    assert result["approved"] is False

    assert (
        "Bid-ask spread exceeds the maximum allowed."
        in result["reasons"]
    )


def test_rejects_low_volume():

    data = valid_option()
    data["volume"] = 10

    result = evaluate_options_risk(**data)

    assert result["approved"] is False


def test_rejects_low_open_interest():

    data = valid_option()
    data["open_interest"] = 100

    result = evaluate_options_risk(**data)

    assert result["approved"] is False


def test_rejects_expiry_day():

    data = valid_option()
    data["days_to_expiry"] = 0

    result = evaluate_options_risk(**data)

    assert result["approved"] is False


def test_warns_on_high_iv():

    data = valid_option()
    data["iv"] = 100

    result = evaluate_options_risk(**data)

    assert (
        "Implied volatility is unusually high."
        in result["warnings"]
    )


def test_insufficient_capital_for_one_lot():

    data = valid_option()

    data["capital"] = 10000
    data["premium"] = 500

    result = evaluate_options_risk(**data)

    assert result["approved"] is False
    assert result["lots"] == 0


def test_invalid_lot_size():

    data = valid_option()
    data["lot_size"] = 0

    with pytest.raises(
        ValueError,
        match="Lot size must be greater than zero",
    ):
        evaluate_options_risk(**data)