from unittest.mock import MagicMock

import pytest

from services.live_option_chain_builder import (
    LiveOptionChainBuilder,
)


def instrument_contract(
    token,
    strike,
    option_type,
    lot_size=75,
):
    """
    Create a realistic mock Angel One
    option instrument-master contract.
    """

    return {
        "token": str(token),
        "symbol": (
            f"NIFTY14JUL26"
            f"{strike}{option_type}"
        ),
        "name": "NIFTY",
        "expiry": "14JUL2026",
        "strike": str(
            strike * 100
        ),
        "lotsize": str(
            lot_size
        ),
        "instrumenttype": "OPTIDX",
        "exch_seg": "NFO",
    }


def make_instruments():
    """
    Build mock CE and PE contracts
    across nearby NIFTY strikes.
    """

    instruments = []

    token = 1000

    for strike in (
        24000,
        24050,
        24100,
        24150,
        24200,
        24250,
        24300,
        24350,
        24400,
    ):
        for option_type in (
            "CE",
            "PE",
        ):
            token += 1

            instruments.append(
                instrument_contract(
                    token=token,
                    strike=strike,
                    option_type=option_type,
                    lot_size=75,
                )
            )

    return instruments


def test_normalize_strike():

    result = (
        LiveOptionChainBuilder
        ._normalize_strike(
            "2420000.000000"
        )
    )

    assert result == 24200


def test_get_nearby_contracts():

    master = MagicMock()

    master.get_nearest_expiry.return_value = {
        "display": "14JUL2026",
        "raw": "14JUL2026",
    }

    master.get_option_contracts.return_value = (
        make_instruments()
    )

    builder = LiveOptionChainBuilder(
        instrument_master=master,
        market_client=MagicMock(),
    )

    result = builder.get_nearby_contracts(
        underlying="NIFTY",
        spot_price=24206,
        strikes_each_side=2,
    )

    strikes = {
        item["_strike"]
        for item in result[
            "contracts"
        ]
    }

    assert strikes == {
        24100,
        24150,
        24200,
        24250,
        24300,
    }

    assert len(
        result["contracts"]
    ) == 10

    for contract in result[
        "contracts"
    ]:
        assert (
            int(
                contract["lotsize"]
            )
            == 75
        )


def test_build_normalized_chain():

    master = MagicMock()

    master.get_nearest_expiry.return_value = {
        "display": "14JUL2026",
        "raw": "14JUL2026",
    }

    master.get_option_contracts.return_value = (
        make_instruments()
    )

    market_client = MagicMock()

    market_client.get_market_data.return_value = {
        "status": True,
        "data": {
            "fetched": [
                {
                    "symbolToken": "1009",
                    "ltp": 150.0,
                    "tradeVolume": 20000,
                    "opnInterest": 30000,
                    "depth": {
                        "buy": [
                            {
                                "price": 149.5
                            }
                        ],
                        "sell": [
                            {
                                "price": 150.5
                            }
                        ],
                    },
                }
            ],
            "unfetched": [],
        },
    }

    builder = LiveOptionChainBuilder(
        instrument_master=master,
        market_client=market_client,
    )

    result = builder.build_chain(
        underlying="NIFTY",
        spot_price=24206,
        strikes_each_side=2,
    )

    assert (
        result["expiry"]
        == "14JUL2026"
    )

    assert (
        result["received_contracts"]
        == 1
    )

    assert (
        result["validated_contracts"]
        == 1
    )

    assert (
        result["rejected_contracts"]
        == 0
    )

    assert (
        result["integrity_validated"]
        is True
    )

    assert len(
        result["contracts"]
    ) == 1

    contract = result[
        "contracts"
    ][0]

    assert (
        contract["premium"]
        == 150.0
    )

    assert (
        contract["bid"]
        == 149.5
    )

    assert (
        contract["ask"]
        == 150.5
    )

    assert (
        contract["open_interest"]
        == 30000
    )

    assert (
        contract["volume"]
        == 20000
    )

    assert (
        contract["lot_size"]
        == 75
    )

    assert (
        contract["option_type"]
        == "CE"
    )

    assert (
        contract["strike"]
        == 24200.0
    )


def test_invalid_spot_price():

    builder = LiveOptionChainBuilder(
        instrument_master=MagicMock(),
        market_client=MagicMock(),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Spot price must be "
            "greater than zero"
        ),
    ):
        builder.get_nearby_contracts(
            underlying="NIFTY",
            spot_price=0,
        )