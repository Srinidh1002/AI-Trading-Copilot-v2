from unittest.mock import MagicMock

import pytest

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

def test_fetch_returns_defensive_copy():
    mock_session = MagicMock()
    mock_response = MagicMock()

    mock_response.json.return_value = (
        sample_instruments()
    )

    mock_session.get.return_value = (
        mock_response
    )

    service = AngelInstrumentMaster(
        session=mock_session,
        time_function=lambda: 1000.0,
    )

    first = service.fetch_instruments()
    first[0]["token"] = "MODIFIED"

    second = service.get_option_contracts(
        "NIFTY"
    )

    assert second[0]["token"] == "1001"


def test_fetch_metadata_contains_source_and_timestamp():
    mock_session = MagicMock()
    mock_response = MagicMock()

    mock_response.json.return_value = (
        sample_instruments()
    )

    mock_session.get.return_value = (
        mock_response
    )

    service = AngelInstrumentMaster(
        session=mock_session,
        time_function=lambda: 1000.0,
    )

    service.fetch_instruments()

    assert service.get_metadata() == {
        "source": (
            "ANGEL_ONE_OPENAPI_SCRIP_MASTER"
        ),
        "source_url": (
            "https://margincalculator.angelone.in/"
            "OpenAPI_File/files/"
            "OpenAPIScripMaster.json"
        ),
        "fetched_at_epoch_seconds": 1000.0,
        "record_count": 4,
        "validated": True,
    }


def test_option_contracts_are_deterministically_ordered():
    instruments = list(
        reversed(
            sample_instruments()
        )
    )

    service = AngelInstrumentMaster()
    service.instruments = instruments

    contracts = service.get_option_contracts(
        "NIFTY"
    )

    assert [
        item["token"]
        for item in contracts
    ] == [
        "1001",
        "1002",
        "1003",
    ]


def test_option_contract_result_is_defensive_copy():
    service = AngelInstrumentMaster()
    service.instruments = sample_instruments()

    first = service.get_option_contracts(
        "NIFTY"
    )

    first[0]["token"] = "MODIFIED"

    second = service.get_option_contracts(
        "NIFTY"
    )

    assert second[0]["token"] == "1001"


def test_duplicate_option_token_is_rejected():
    instruments = sample_instruments()

    duplicate = dict(
        instruments[0]
    )

    duplicate["symbol"] = (
        "NIFTY14JUL2624250CE"
    )

    instruments.append(
        duplicate
    )

    service = AngelInstrumentMaster()
    service.instruments = instruments

    with pytest.raises(
        RuntimeError,
        match="Duplicate Angel option token",
    ):
        service.get_option_contracts(
            "NIFTY"
        )


def test_duplicate_option_symbol_is_rejected():
    instruments = sample_instruments()

    duplicate = dict(
        instruments[0]
    )

    duplicate["token"] = "DIFFERENT"

    instruments.append(
        duplicate
    )

    service = AngelInstrumentMaster()
    service.instruments = instruments

    with pytest.raises(
        RuntimeError,
        match="Duplicate Angel option symbol",
    ):
        service.get_option_contracts(
            "NIFTY"
        )


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    (
        ("token", ""),
        ("symbol", ""),
        ("expiry", "invalid"),
        ("strike", "invalid"),
        ("strike", "0"),
        ("strike", "nan"),
        ("lotsize", "0"),
        ("lotsize", "10.5"),
        ("lotsize", "invalid"),
    ),
)
def test_malformed_matching_option_contract_is_rejected(
    field,
    value,
):
    instruments = sample_instruments()

    instruments[0] = dict(
        instruments[0]
    )

    instruments[0][field] = value

    service = AngelInstrumentMaster()
    service.instruments = instruments

    with pytest.raises(RuntimeError):
        service.get_option_contracts(
            "NIFTY"
        )


def test_non_matching_malformed_record_does_not_pollute_market():
    instruments = sample_instruments()

    instruments.append(
        {
            "name": "OTHER",
            "exch_seg": "MCX",
            "instrumenttype": "FUTCOM",
        }
    )

    service = AngelInstrumentMaster()
    service.instruments = instruments

    contracts = service.get_option_contracts(
        "NIFTY",
        exchange="NFO",
    )

    assert len(contracts) == 3


@pytest.mark.parametrize(
    "payload",
    (
        {},
        None,
        "invalid",
        [],
        [None],
    ),
)
def test_invalid_download_payload_fails_closed(
    payload,
):
    mock_session = MagicMock()
    mock_response = MagicMock()

    mock_response.json.return_value = payload
    mock_session.get.return_value = mock_response

    service = AngelInstrumentMaster(
        session=mock_session
    )

    with pytest.raises(RuntimeError):
        service.fetch_instruments()
