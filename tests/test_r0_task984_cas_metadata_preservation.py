from unittest.mock import MagicMock

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)


def test_angel_master_preserves_cas_metadata_without_interpretation():
    records = [
        {
            "token": "1001",
            "symbol": "NIFTY27AUG2624500CE",
            "name": "NIFTY",
            "expiry": "27AUG2026",
            "strike": "2450000.000000",
            "lotsize": "75",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
            "is_cas_enabled": True,
            "referenceLimitPrice": "999.99",
        },
        {
            "token": "2001",
            "symbol": "SENSEX27AUG2678500CE",
            "name": "SENSEX",
            "expiry": "27AUG2026",
            "strike": "7850000.000000",
            "lotsize": "20",
            "instrumenttype": "OPTIDX",
            "exch_seg": "BFO",
            "is_cas_enabled": False,
        },
    ]

    response = MagicMock()
    response.json.return_value = records

    session = MagicMock()
    session.get.return_value = response

    master = AngelInstrumentMaster(
        session=session,
        time_function=lambda: 1000.0,
    )

    fetched = master.fetch_instruments()

    assert (
        fetched[0]["is_cas_enabled"]
        is True
    )

    assert (
        fetched[1]["is_cas_enabled"]
        is False
    )

    # Provider field remains evidence only. Master does not
    # reinterpret this reference value as normal LTP.
    assert (
        fetched[0]["referenceLimitPrice"]
        == "999.99"
    )

    contracts = (
        master.get_option_contracts(
            "NIFTY",
            exchange="NFO",
        )
    )

    assert (
        contracts[0][
            "is_cas_enabled"
        ]
        is True
    )

    assert (
        contracts[0][
            "referenceLimitPrice"
        ]
        == "999.99"
    )
