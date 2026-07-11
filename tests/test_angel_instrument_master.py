from unittest.mock import MagicMock

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)


def sample_instruments():
    return [
        {
            "token": "1001",
            "symbol": "NIFTY14JUL2624200CE",
            "name": "NIFTY",
            "expiry": "14JUL2026",
            "strike": "2420000.000000",
            "lotsize": "75",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
        },
        {
            "token": "1002",
            "symbol": "NIFTY14JUL2624200PE",
            "name": "NIFTY",
            "expiry": "14JUL2026",
            "strike": "2420000.000000",
            "lotsize": "75",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
        },
        {
            "token": "1003",
            "symbol": "NIFTY21JUL2624200CE",
            "name": "NIFTY",
            "expiry": "21JUL2026",
            "strike": "2420000.000000",
            "lotsize": "75",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
        },
        {
            "token": "2001",
            "symbol": "BANKNIFTY29JUL2650000CE",
            "name": "BANKNIFTY",
            "expiry": "29JUL2026",
            "strike": "5000000.000000",
            "lotsize": "30",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
        },
    ]


def test_fetch_instruments():

    mock_session = MagicMock()
    mock_response = MagicMock()

    mock_response.json.return_value = (
        sample_instruments()
    )

    mock_session.get.return_value = (
        mock_response
    )

    service = AngelInstrumentMaster(
        session=mock_session
    )

    result = service.fetch_instruments()

    assert len(result) == 4

    mock_response.raise_for_status.assert_called_once()


def test_get_nifty_option_contracts():

    service = AngelInstrumentMaster()

    service.instruments = (
        sample_instruments()
    )

    result = service.get_option_contracts(
        "NIFTY"
    )

    assert len(result) == 3

    assert all(
        item["name"] == "NIFTY"
        for item in result
    )


def test_filters_other_underlyings():

    service = AngelInstrumentMaster()

    service.instruments = (
        sample_instruments()
    )

    result = service.get_option_contracts(
        "BANKNIFTY"
    )

    assert len(result) == 1


def test_parse_expiry():

    result = (
        AngelInstrumentMaster
        ._parse_expiry(
            "14JUL2026"
        )
    )

    assert result.year == 2026
    assert result.month == 7
    assert result.day == 14