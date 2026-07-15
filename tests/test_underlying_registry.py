from dataclasses import FrozenInstanceError

import pytest

from services.underlying_registry import (
    UnderlyingConfiguration,
)
from services.underlying_registry import (
    UnderlyingRegistry,
)


def test_nifty_configuration_is_registered():
    configuration = (
        UnderlyingRegistry.get(
            "NIFTY"
        )
    )

    assert isinstance(
        configuration,
        UnderlyingConfiguration,
    )

    assert (
        configuration.underlying
        == "NIFTY"
    )

    assert (
        configuration.exchange
        == "NSE"
    )

    assert (
        configuration.symboltoken
        == "99926000"
    )

    assert (
        configuration.option_exchange
        == "NFO"
    )


def test_underlying_lookup_is_normalized():
    configuration = (
        UnderlyingRegistry.get(
            "  nifty  "
        )
    )

    assert (
        configuration.underlying
        == "NIFTY"
    )


def test_default_underlying_is_nifty():
    configuration = (
        UnderlyingRegistry.get()
    )

    assert (
        configuration.underlying
        == "NIFTY"
    )


def test_configuration_is_immutable():
    configuration = (
        UnderlyingRegistry.get(
            "NIFTY"
        )
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        configuration.exchange = "BSE"


def test_unsupported_underlying_fails_closed():
    with pytest.raises(
        ValueError,
        match=(
            "Unsupported underlying: "
            "SENSEX."
        ),
    ):
        UnderlyingRegistry.get(
            "SENSEX"
        )


@pytest.mark.parametrize(
    "underlying",
    [
        "",
        " ",
    ],
)
def test_empty_underlying_is_rejected(
    underlying,
):
    with pytest.raises(
        ValueError,
        match=(
            "underlying cannot be empty."
        ),
    ):
        UnderlyingRegistry.get(
            underlying
        )


@pytest.mark.parametrize(
    "underlying",
    [
        123,
        True,
        [],
        {},
    ],
)
def test_non_string_underlying_is_rejected(
    underlying,
):
    with pytest.raises(
        ValueError,
        match=(
            "underlying must be a string."
        ),
    ):
        UnderlyingRegistry.get(
            underlying
        )


def test_supported_underlyings_are_returned():
    assert (
        UnderlyingRegistry
        .supported_underlyings()
        == (
            "NIFTY",
        )
    )


def test_is_supported_returns_true_for_nifty():
    assert (
        UnderlyingRegistry.is_supported(
            "nifty"
        )
        is True
    )


@pytest.mark.parametrize(
    "underlying",
    [
        "SENSEX",
        "",
        None,
        123,
        True,
    ],
)
def test_is_supported_returns_false(
    underlying,
):
    assert (
        UnderlyingRegistry.is_supported(
            underlying
        )
        is False
    )


def test_get_dict_returns_detached_dictionary():
    configuration = (
        UnderlyingRegistry.get_dict(
            "NIFTY"
        )
    )

    configuration[
        "exchange"
    ] = "CHANGED"

    original = (
        UnderlyingRegistry.get(
            "NIFTY"
        )
    )

    assert (
        original.exchange
        == "NSE"
    )
