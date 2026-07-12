import pytest

from services.option_chain_validator import (
    OptionChainValidationError,
    validate_option_chain,
    validate_option_contract,
)


def valid_contract():
    return {
        "token": "12345",
        "symbol": "NIFTY14JUL2624200CE",
        "strike": 24200,
        "option_type": "CE",
        "expiry": "14JUL2026",
        "lot_size": 75,
        "premium": 101.15,
        "bid": 100.90,
        "ask": 101.20,
        "volume": 10000,
        "open_interest": 50000,
        "delta": None,
        "gamma": None,
        "theta": None,
        "vega": None,
        "iv": None,
    }


def test_valid_option_contract_passes():

    result = validate_option_contract(
        valid_contract()
    )

    assert result["symbol"] == (
        "NIFTY14JUL2624200CE"
    )

    assert result["option_type"] == "CE"

    assert result["strike"] == 24200.0

    assert result["lot_size"] == 75


def test_rejects_non_dictionary_contract():

    with pytest.raises(
        OptionChainValidationError,
        match="dictionary",
    ):
        validate_option_contract(
            "invalid"
        )


def test_rejects_missing_symbol():

    contract = valid_contract()

    contract["symbol"] = ""

    with pytest.raises(
        OptionChainValidationError,
        match="symbol is required",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_invalid_option_type():

    contract = valid_contract()

    contract["option_type"] = "INVALID"

    with pytest.raises(
        OptionChainValidationError,
        match="CE or PE",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_zero_strike():

    contract = valid_contract()

    contract["strike"] = 0

    with pytest.raises(
        OptionChainValidationError,
        match="Strike must be greater than zero",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_zero_premium():

    contract = valid_contract()

    contract["premium"] = 0

    with pytest.raises(
        OptionChainValidationError,
        match="Premium must be greater than zero",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_ask_below_bid():

    contract = valid_contract()

    contract["bid"] = 105

    contract["ask"] = 100

    with pytest.raises(
        OptionChainValidationError,
        match="Ask cannot be below Bid",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_negative_volume():

    contract = valid_contract()

    contract["volume"] = -1

    with pytest.raises(
        OptionChainValidationError,
        match="Volume cannot be negative",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_negative_open_interest():

    contract = valid_contract()

    contract["open_interest"] = -1

    with pytest.raises(
        OptionChainValidationError,
        match="Open interest cannot be negative",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_invalid_lot_size():

    contract = valid_contract()

    contract["lot_size"] = 0

    with pytest.raises(
        OptionChainValidationError,
        match="Lot size must be greater than zero",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_nan_premium():

    contract = valid_contract()

    contract["premium"] = float(
        "nan"
    )

    with pytest.raises(
        OptionChainValidationError,
        match="Premium must be finite",
    ):
        validate_option_contract(
            contract
        )


def test_rejects_infinite_bid():

    contract = valid_contract()

    contract["bid"] = float(
        "inf"
    )

    with pytest.raises(
        OptionChainValidationError,
        match="Bid must be finite",
    ):
        validate_option_contract(
            contract
        )


def test_optional_greeks_may_be_none():

    contract = valid_contract()

    result = validate_option_contract(
        contract
    )

    assert result["delta"] is None
    assert result["gamma"] is None
    assert result["theta"] is None
    assert result["vega"] is None
    assert result["iv"] is None


def test_valid_optional_greeks_are_normalized():

    contract = valid_contract()

    contract["delta"] = "0.52"
    contract["gamma"] = "0.01"
    contract["theta"] = "-12.5"
    contract["vega"] = "8.4"
    contract["iv"] = "14.2"

    result = validate_option_contract(
        contract
    )

    assert result["delta"] == 0.52
    assert result["gamma"] == 0.01
    assert result["theta"] == -12.5
    assert result["vega"] == 8.4
    assert result["iv"] == 14.2


def test_chain_rejects_invalid_contract_and_keeps_valid():

    invalid = valid_contract()

    invalid["symbol"] = (
        "NIFTY14JUL2624300CE"
    )

    invalid["premium"] = 0

    result = validate_option_chain([
        invalid,
        valid_contract(),
    ])

    assert len(result) == 1

    assert (
        result[0]["symbol"]
        == "NIFTY14JUL2624200CE"
    )


def test_chain_removes_duplicate_contracts():

    first = valid_contract()

    duplicate = dict(
        first
    )

    result = validate_option_chain([
        first,
        duplicate,
    ])

    assert len(result) == 1


def test_chain_fails_when_all_contracts_invalid():

    contract = valid_contract()

    contract["premium"] = 0

    with pytest.raises(
        OptionChainValidationError,
        match="No valid option contracts remain",
    ):
        validate_option_chain([
            contract
        ])


def test_rejects_empty_chain():

    with pytest.raises(
        OptionChainValidationError,
        match="cannot be empty",
    ):
        validate_option_chain(
            []
        )