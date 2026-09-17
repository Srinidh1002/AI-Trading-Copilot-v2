from __future__ import annotations

from dataclasses import dataclass


_SUPPORTED = {
    ("NIFTY", "NFO"),
    ("SENSEX", "BFO"),
}


@dataclass(frozen=True, slots=True)
class AngelOptionProviderCapabilities:
    underlying_symbol: str
    option_exchange: str
    option_greeks_supported: bool
    option_greeks_required: bool = False
    provider_name: str = "ANGEL_ONE"

    def __post_init__(self) -> None:
        underlying = str(
            self.underlying_symbol
        ).strip().upper()

        exchange = str(
            self.option_exchange
        ).strip().upper()

        if (
            underlying,
            exchange,
        ) not in _SUPPORTED:
            raise ValueError(
                "unsupported Angel option capability identity"
            )

        if self.option_greeks_required:
            if not self.option_greeks_supported:
                raise ValueError(
                    "required option Greeks must be supported"
                )

        object.__setattr__(
            self,
            "underlying_symbol",
            underlying,
        )

        object.__setattr__(
            self,
            "option_exchange",
            exchange,
        )


def angel_option_provider_capabilities(
    underlying_symbol: str,
    option_exchange: str | None = None,
) -> AngelOptionProviderCapabilities:
    underlying = str(
        underlying_symbol
    ).strip().upper()

    expected_exchange = {
        "NIFTY": "NFO",
        "SENSEX": "BFO",
    }.get(underlying)

    if expected_exchange is None:
        raise ValueError(
            "only NIFTY and SENSEX option capabilities are supported"
        )

    exchange = (
        expected_exchange
        if option_exchange is None
        else str(
            option_exchange
        ).strip().upper()
    )

    if exchange != expected_exchange:
        raise ValueError(
            "option exchange does not match underlying"
        )

    if underlying == "NIFTY":
        return AngelOptionProviderCapabilities(
            underlying_symbol=underlying,
            option_exchange=exchange,
            option_greeks_supported=True,
            option_greeks_required=False,
        )

    return AngelOptionProviderCapabilities(
        underlying_symbol=underlying,
        option_exchange=exchange,
        option_greeks_supported=False,
        option_greeks_required=False,
    )


__all__ = [
    "AngelOptionProviderCapabilities",
    "angel_option_provider_capabilities",
]
