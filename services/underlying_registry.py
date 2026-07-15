"""
Central registry for supported trading underlyings.

The registry owns the canonical relationship between:

- underlying name
- spot market-data exchange
- spot symbol token
- option exchange

This module does not fetch market data.
This module does not place orders.
This module does not authorize trades.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from dataclasses import dataclass


@dataclass(
    frozen=True
)
class UnderlyingConfiguration:
    """
    Immutable broker-market identity for one underlying.
    """

    underlying: str
    exchange: str
    symboltoken: str
    option_exchange: str


class UnderlyingRegistry:
    """
    Resolve canonical configuration for supported underlyings.
    """

    DEFAULT_UNDERLYING = "NIFTY"

    _CONFIGURATIONS = {
        "NIFTY": UnderlyingConfiguration(
            underlying="NIFTY",
            exchange="NSE",
            symboltoken="99926000",
            option_exchange="NFO",
        ),
        "SENSEX": UnderlyingConfiguration(
            underlying="SENSEX",
            exchange="BSE",
            symboltoken="99919000",
            option_exchange="BFO",
        ),
    }

    @classmethod
    def _normalize_underlying(
        cls,
        underlying,
    ):
        if not isinstance(
            underlying,
            str,
        ):
            raise ValueError(
                "underlying must be a string."
            )

        normalized = (
            underlying
            .strip()
            .upper()
        )

        if not normalized:
            raise ValueError(
                "underlying cannot be empty."
            )

        return normalized

    @classmethod
    def get(
        cls,
        underlying=None,
    ):
        """
        Return immutable configuration for one underlying.
        """

        if underlying is None:
            underlying = (
                cls.DEFAULT_UNDERLYING
            )

        normalized = (
            cls._normalize_underlying(
                underlying
            )
        )

        configuration = (
            cls._CONFIGURATIONS.get(
                normalized
            )
        )

        if configuration is None:
            raise ValueError(
                "Unsupported underlying: "
                f"{normalized}."
            )

        return configuration

    @classmethod
    def get_dict(
        cls,
        underlying=None,
    ):
        """
        Return a detached dictionary representation.
        """

        return deepcopy(
            asdict(
                cls.get(
                    underlying
                )
            )
        )

    @classmethod
    def supported_underlyings(
        cls,
    ):
        """
        Return supported underlying names.
        """

        return tuple(
            sorted(
                cls._CONFIGURATIONS.keys()
            )
        )

    @classmethod
    def is_supported(
        cls,
        underlying,
    ):
        """
        Return whether an underlying is registered.
        """

        try:
            normalized = (
                cls._normalize_underlying(
                    underlying
                )
            )

        except ValueError:
            return False

        return (
            normalized
            in cls._CONFIGURATIONS
        )
