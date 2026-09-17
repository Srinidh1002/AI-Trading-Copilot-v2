from unittest.mock import MagicMock

import pytest

from services.angel_instrument_master import (
    AngelInstrumentMaster,
)


def _instruments():
    return [
        {
            "token": "1001",
            "symbol": "NIFTY10AUG2625000CE",
            "name": "NIFTY",
            "expiry": "10AUG2026",
            "strike": "2500000.000000",
            "lotsize": "75",
            "instrumenttype": "OPTIDX",
            "exch_seg": "NFO",
        },
        {
            "token": "2001",
            "symbol": "SENSEX13AUG2680000CE",
            "name": "SENSEX",
            "expiry": "13AUG2026",
            "strike": "8000000.000000",
            "lotsize": "20",
            "instrumenttype": "OPTIDX",
            "exch_seg": "BFO",
        },
    ]


class MutableClock:
    def __init__(self, value):
        self.value = float(value)

    def __call__(self):
        return self.value


def _fetched_master(clock):
    response = MagicMock()
    response.json.return_value = _instruments()

    session = MagicMock()
    session.get.return_value = response

    master = AngelInstrumentMaster(
        session=session,
        time_function=clock,
    )

    master.fetch_instruments()

    return master


def test_fresh_provider_master_is_accepted():
    clock = MutableClock(1000.0)

    master = _fetched_master(clock)

    clock.value = 1001.0

    contracts = master.get_option_contracts(
        "NIFTY",
        exchange="NFO",
    )

    assert len(contracts) == 1
    assert contracts[0]["token"] == "1001"


def test_provider_master_older_than_limit_is_rejected():
    clock = MutableClock(1000.0)

    master = _fetched_master(clock)

    clock.value = (
        1000.0
        + master.DEFAULT_MAXIMUM_MASTER_AGE_SECONDS
        + 0.001
    )

    with pytest.raises(
        RuntimeError,
        match="instrument master is stale",
    ):
        master.get_option_contracts(
            "NIFTY",
            exchange="NFO",
        )


def test_master_exactly_at_age_limit_is_allowed():
    clock = MutableClock(1000.0)

    master = _fetched_master(clock)

    clock.value = (
        1000.0
        + master.DEFAULT_MAXIMUM_MASTER_AGE_SECONDS
    )

    contracts = master.get_option_contracts(
        "SENSEX",
        exchange="BFO",
    )

    assert len(contracts) == 1


def test_future_provider_master_timestamp_is_rejected():
    clock = MutableClock(1000.0)

    master = _fetched_master(clock)

    clock.value = 999.0

    with pytest.raises(
        RuntimeError,
        match="timestamp is in the future",
    ):
        master.get_option_contracts(
            "NIFTY",
            exchange="NFO",
        )


def test_explicit_injected_fixture_remains_supported():
    master = AngelInstrumentMaster(
        time_function=lambda: 999999999.0,
    )

    master.instruments = _instruments()

    contracts = master.get_option_contracts(
        "NIFTY",
        exchange="NFO",
    )

    assert len(contracts) == 1

    metadata = master.get_metadata()

    assert metadata["injected_fixture"] is True
    assert metadata["validated"] is False


@pytest.mark.parametrize(
    "value",
    (
        0,
        -1,
        True,
        float("inf"),
        float("nan"),
    ),
)
def test_invalid_master_age_configuration_is_rejected(
    value,
):
    with pytest.raises(ValueError):
        AngelInstrumentMaster(
            maximum_master_age_seconds=value,
        )


def test_wrong_derivative_segment_cannot_cross_resolve():
    master = AngelInstrumentMaster()

    master.instruments = _instruments()

    assert (
        master.get_option_contracts(
            "NIFTY",
            exchange="BFO",
        )
        == []
    )

    assert (
        master.get_option_contracts(
            "SENSEX",
            exchange="NFO",
        )
        == []
    )
