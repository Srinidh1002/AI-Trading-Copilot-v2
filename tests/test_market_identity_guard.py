from dataclasses import replace

from services.live_market_configuration import (
    resolve_live_market_configuration,
)
from services.market_identity_guard import (
    validate_market_identity,
)
from services.market_session_configuration import (
    resolve_market_session_configuration,
)


def test_nifty_market_identity_is_consistent():
    market_configuration = (
        resolve_live_market_configuration(
            "NIFTY"
        )
    )

    session_configuration = (
        resolve_market_session_configuration(
            "NIFTY"
        )
    )

    result = validate_market_identity(
        market_configuration,
        session_configuration,
    )

    assert result == {
        "valid": True,
        "underlying": "NIFTY",
        "exchange": "NSE",
        "option_exchange": "NFO",
    }


def test_sensex_market_identity_is_consistent():
    market_configuration = (
        resolve_live_market_configuration(
            "SENSEX"
        )
    )

    session_configuration = (
        resolve_market_session_configuration(
            "SENSEX"
        )
    )

    result = validate_market_identity(
        market_configuration,
        session_configuration,
    )

    assert result == {
        "valid": True,
        "underlying": "SENSEX",
        "exchange": "BSE",
        "option_exchange": "BFO",
    }


def test_crossed_nifty_and_sensex_configuration_is_rejected():
    market_configuration = (
        resolve_live_market_configuration(
            "NIFTY"
        )
    )

    session_configuration = (
        resolve_market_session_configuration(
            "SENSEX"
        )
    )

    try:
        validate_market_identity(
            market_configuration,
            session_configuration,
        )

    except ValueError as exc:
        message = str(
            exc
        )

        assert (
            "underlying"
            in message
        )

        assert (
            "exchange"
            in message
        )

        assert (
            "option_exchange"
            in message
        )

    else:
        raise AssertionError(
            "Expected crossed market identity "
            "to be rejected."
        )


def test_spot_exchange_mismatch_is_rejected():
    market_configuration = (
        resolve_live_market_configuration(
            "NIFTY"
        )
    )

    session_configuration = (
        resolve_market_session_configuration(
            "NIFTY"
        )
    )

    invalid_session = replace(
        session_configuration,
        exchange="BSE",
    )

    try:
        validate_market_identity(
            market_configuration,
            invalid_session,
        )

    except ValueError as exc:
        assert (
            str(
                exc
            )
            == (
                "Market identity mismatch: "
                "exchange."
            )
        )

    else:
        raise AssertionError(
            "Expected exchange mismatch rejection."
        )


def test_option_exchange_mismatch_is_rejected():
    market_configuration = (
        resolve_live_market_configuration(
            "SENSEX"
        )
    )

    session_configuration = (
        resolve_market_session_configuration(
            "SENSEX"
        )
    )

    invalid_session = replace(
        session_configuration,
        option_exchange="NFO",
    )

    try:
        validate_market_identity(
            market_configuration,
            invalid_session,
        )

    except ValueError as exc:
        assert (
            str(
                exc
            )
            == (
                "Market identity mismatch: "
                "option_exchange."
            )
        )

    else:
        raise AssertionError(
            "Expected option exchange mismatch "
            "rejection."
        )


def test_underlying_mismatch_is_rejected():
    market_configuration = (
        resolve_live_market_configuration(
            "NIFTY"
        )
    )

    session_configuration = (
        resolve_market_session_configuration(
            "NIFTY"
        )
    )

    invalid_session = replace(
        session_configuration,
        underlying="SENSEX",
    )

    try:
        validate_market_identity(
            market_configuration,
            invalid_session,
        )

    except ValueError as exc:
        assert (
            str(
                exc
            )
            == (
                "Market identity mismatch: "
                "underlying."
            )
        )

    else:
        raise AssertionError(
            "Expected underlying mismatch rejection."
        )


def test_missing_market_configuration_is_rejected():
    session_configuration = (
        resolve_market_session_configuration(
            "NIFTY"
        )
    )

    try:
        validate_market_identity(
            None,
            session_configuration,
        )

    except ValueError as exc:
        assert (
            str(
                exc
            )
            == (
                "Market configuration is required."
            )
        )

    else:
        raise AssertionError(
            "Expected missing market configuration "
            "rejection."
        )


def test_missing_session_configuration_is_rejected():
    market_configuration = (
        resolve_live_market_configuration(
            "NIFTY"
        )
    )

    try:
        validate_market_identity(
            market_configuration,
            None,
        )

    except ValueError as exc:
        assert (
            str(
                exc
            )
            == (
                "Session configuration is required."
            )
        )

    else:
        raise AssertionError(
            "Expected missing session configuration "
            "rejection."
        )
