import pytest

from services.option_contract_selector import (
    select_option_contract,
)


def contracts():
    return [
        {
            "symbol": "NIFTY-ATM-CE",
            "strike": 24200,
            "option_type": "CE",
            "expiry": "2026-07-16",
            "premium": 150,
            "bid": 149.5,
            "ask": 150.5,
            "volume": 20000,
            "open_interest": 30000,
            "delta": 0.55,
            "iv": 18,
        },
        {
            "symbol": "NIFTY-OTM-CE",
            "strike": 24500,
            "option_type": "CE",
            "expiry": "2026-07-16",
            "premium": 50,
            "bid": 49,
            "ask": 51,
            "volume": 5000,
            "open_interest": 10000,
            "delta": 0.30,
            "iv": 20,
        },
        {
            "symbol": "NIFTY-ATM-PE",
            "strike": 24200,
            "option_type": "PE",
            "expiry": "2026-07-16",
            "premium": 140,
            "bid": 139.5,
            "ask": 140.5,
            "volume": 18000,
            "open_interest": 25000,
            "delta": -0.50,
            "iv": 19,
        },
    ]


def test_bullish_selects_call():

    result = select_option_contract(
        contracts=contracts(),
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is True
    assert result["option_type"] == "CE"
    assert result["symbol"] == (
        "NIFTY-ATM-CE"
    )


def test_bearish_selects_put():

    result = select_option_contract(
        contracts=contracts(),
        direction="BEARISH",
        spot_price=24206,
    )

    assert result["selected"] is True
    assert result["option_type"] == "PE"


def test_neutral_returns_no_contract():

    result = select_option_contract(
        contracts=contracts(),
        direction="NEUTRAL",
        spot_price=24206,
    )

    assert result["selected"] is False
    assert (
        result["decision"]
        == "NO_CONTRACT"
    )


def test_empty_contracts():

    result = select_option_contract(
        contracts=[],
        direction="BULLISH",
        spot_price=24206,
    )

    assert result["selected"] is False


def test_rejects_illiquid_contract():

    data = [
        {
            "symbol": "BAD-CE",
            "strike": 24200,
            "option_type": "CE",
            "expiry": "2026-07-16",
            "premium": 100,
            "bid": 99,
            "ask": 101,
            "volume": 10,
            "open_interest": 10,
            "delta": 0.50,
        }
    ]

    result = select_option_contract(
        contracts=data,
        direction="BULLISH",
        spot_price=24200,
    )

    assert result["selected"] is False


def test_rejects_wide_spread():

    data = contracts()

    data[0]["bid"] = 130
    data[0]["ask"] = 170

    result = select_option_contract(
        contracts=data,
        direction="BULLISH",
        spot_price=24200,
    )

    assert (
        result["symbol"]
        != "NIFTY-ATM-CE"
    )


def test_invalid_spot_price():

    with pytest.raises(
        ValueError,
        match="Spot price must be greater than zero",
    ):
        select_option_contract(
            contracts=contracts(),
            direction="BULLISH",
            spot_price=0,
        )
def test_allows_missing_delta_when_optional():

    data = contracts()

    data[0]["delta"] = None

    result = select_option_contract(
        contracts=data,
        direction="BULLISH",
        spot_price=24206,
        require_delta=False,
    )

    assert result["selected"] is True
    assert result["option_type"] == "CE"


def test_rejects_missing_delta_when_required():

    data = contracts()

    for contract in data:
        contract["delta"] = None

    result = select_option_contract(
        contracts=data,
        direction="BULLISH",
        spot_price=24206,
        require_delta=True,
    )

    assert result["selected"] is False