"""
Live market configuration boundary.

Resolves a requested live option underlying through the
canonical UnderlyingRegistry before the live runner uses it.
"""

from services.underlying_registry import (
    UnderlyingRegistry,
)


DEFAULT_LIVE_UNDERLYING = "NIFTY"


def resolve_live_market_configuration(
    underlying=None,
):
    requested_underlying = (
        underlying
        if underlying is not None
        else DEFAULT_LIVE_UNDERLYING
    )

    normalized_underlying = (
        str(
            requested_underlying
        )
        .strip()
        .upper()
    )

    if not normalized_underlying:
        raise ValueError(
            "Live underlying cannot be empty."
        )

    return UnderlyingRegistry.get(
        normalized_underlying
    )
