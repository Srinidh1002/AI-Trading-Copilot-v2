from services.live_market_configuration import (
    DEFAULT_LIVE_UNDERLYING,
    resolve_live_market_configuration,
)


def test_default_live_underlying_is_nifty():
    assert (
        DEFAULT_LIVE_UNDERLYING
        == "NIFTY"
    )


def test_default_configuration_resolves_nifty():
    configuration = (
        resolve_live_market_configuration()
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


def test_explicit_nifty_configuration():
    configuration = (
        resolve_live_market_configuration(
            "NIFTY"
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
        configuration.option_exchange
        == "NFO"
    )


def test_explicit_sensex_configuration():
    configuration = (
        resolve_live_market_configuration(
            "SENSEX"
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


def test_underlying_is_normalized():
    configuration = (
        resolve_live_market_configuration(
            "  sensex  "
        )
    )

    assert (
        configuration.underlying
        == "SENSEX"
    )


def test_empty_underlying_is_rejected():
    try:
        resolve_live_market_configuration(
            "   "
        )

    except ValueError as exc:
        assert (
            str(
                exc
            )
            == "Live underlying cannot be empty."
        )

    else:
        raise AssertionError(
            "Expected empty underlying rejection."
        )


def test_unknown_underlying_is_rejected():
    try:
        resolve_live_market_configuration(
            "BANKNIFTY"
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Expected unknown underlying rejection."
        )
