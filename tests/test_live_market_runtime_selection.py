import sys

import pytest

from services.live_market_configuration import (
    resolve_live_market_configuration,
)


def parse_underlying_argument(
    argv,
):
    import argparse

    parser = argparse.ArgumentParser(
        add_help=False,
    )

    parser.add_argument(
        "--underlying",
        default=None,
    )

    arguments, _ = (
        parser.parse_known_args(
            argv
        )
    )

    return arguments.underlying


def resolve_configuration_from_argv(
    argv,
):
    return resolve_live_market_configuration(
        parse_underlying_argument(
            argv
        )
    )


def test_runtime_selection_defaults_to_nifty():
    configuration = (
        resolve_configuration_from_argv(
            []
        )
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


def test_runtime_selection_accepts_nifty():
    configuration = (
        resolve_configuration_from_argv(
            [
                "--underlying",
                "NIFTY",
            ]
        )
    )

    assert (
        configuration.underlying
        == "NIFTY"
    )


def test_runtime_selection_accepts_sensex():
    configuration = (
        resolve_configuration_from_argv(
            [
                "--underlying",
                "SENSEX",
            ]
        )
    )

    assert (
        configuration.underlying
        == "SENSEX"
    )

    assert (
        configuration.exchange
        == "BSE"
    )

    assert (
        configuration.symboltoken
        == "99919000"
    )

    assert (
        configuration.option_exchange
        == "BFO"
    )


def test_runtime_selection_normalizes_sensex():
    configuration = (
        resolve_configuration_from_argv(
            [
                "--underlying",
                "  sensex  ",
            ]
        )
    )

    assert (
        configuration.underlying
        == "SENSEX"
    )


def test_runtime_selection_rejects_unknown_underlying():
    with pytest.raises(
        ValueError,
        match="Unsupported underlying",
    ):
        resolve_configuration_from_argv(
            [
                "--underlying",
                "BANKNIFTY",
            ]
        )


def test_runtime_selection_ignores_unrelated_arguments():
    configuration = (
        resolve_configuration_from_argv(
            [
                "--unrelated",
                "value",
                "--underlying",
                "SENSEX",
            ]
        )
    )

    assert (
        configuration.underlying
        == "SENSEX"
    )
