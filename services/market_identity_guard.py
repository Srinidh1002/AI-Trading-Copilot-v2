"""
Market identity consistency guard.

Validates that live market configuration and market-session
configuration describe the same underlying and exchange route.
"""


def validate_market_identity(
    market_configuration,
    session_configuration,
):
    if market_configuration is None:
        raise ValueError(
            "Market configuration is required."
        )

    if session_configuration is None:
        raise ValueError(
            "Session configuration is required."
        )

    market_underlying = str(
        market_configuration.underlying
    ).strip().upper()

    session_underlying = str(
        session_configuration.underlying
    ).strip().upper()

    market_exchange = str(
        market_configuration.exchange
    ).strip().upper()

    session_exchange = str(
        session_configuration.exchange
    ).strip().upper()

    market_option_exchange = str(
        market_configuration.option_exchange
    ).strip().upper()

    session_option_exchange = str(
        session_configuration.option_exchange
    ).strip().upper()

    mismatches = []

    if (
        market_underlying
        != session_underlying
    ):
        mismatches.append(
            "underlying"
        )

    if (
        market_exchange
        != session_exchange
    ):
        mismatches.append(
            "exchange"
        )

    if (
        market_option_exchange
        != session_option_exchange
    ):
        mismatches.append(
            "option_exchange"
        )

    if mismatches:
        mismatch_text = ", ".join(
            mismatches
        )

        raise ValueError(
            "Market identity mismatch: "
            f"{mismatch_text}."
        )

    return {
        "valid": True,
        "underlying": market_underlying,
        "exchange": market_exchange,
        "option_exchange": (
            market_option_exchange
        ),
    }
