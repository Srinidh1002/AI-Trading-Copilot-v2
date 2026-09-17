"""Injectable provider-capability facts; unknown live behavior remains unknown."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


STATES = frozenset(
    {
        "SUPPORTED",
        "UNSUPPORTED",
        "UNVERIFIED_LIVE",
        "OPTIONAL",
        "DERIVED",
    }
)

FIELDS = (
    "spot",
    "provider_timestamp",
    "5m_candles",
    "15m_candles",
    "1h_candles",
    "1d_candles",
    "option_universe",
    "premium_ltp",
    "oi",
    "provider_oi_change",
    "derived_oi_change",
    "volume",
    "bid",
    "ask",
    "spread",
    "iv",
    "greeks",
    "india_vix_applicability",
)

IDENTITIES = frozenset(
    {
        ("NIFTY", "NSE", "NFO"),
        ("SENSEX", "BSE", "BFO"),
    }
)


@dataclass(frozen=True, slots=True)
class ProviderCapabilityRegistryV1:
    capabilities: Mapping[
        tuple[str, str, str],
        Mapping[str, str],
    ]
    version: str = "provider-capability-registry.v1"

    def __post_init__(self) -> None:
        mapped: dict[
            tuple[str, str, str],
            Mapping[str, str],
        ] = {}

        for identity, fields in self.capabilities.items():
            normalized_identity = tuple(
                str(item).upper()
                for item in identity
            )

            if normalized_identity not in IDENTITIES:
                raise ValueError(
                    "invalid provider capability registry"
                )

            if set(fields) != set(FIELDS):
                raise ValueError(
                    "invalid provider capability registry"
                )

            if any(
                state not in STATES
                for state in fields.values()
            ):
                raise ValueError(
                    "invalid provider capability registry"
                )

            mapped[
                normalized_identity
            ] = MappingProxyType(
                dict(fields)
            )

        if set(mapped) != IDENTITIES:
            raise ValueError(
                "both NIFTY and SENSEX capability rows required"
            )

        object.__setattr__(
            self,
            "capabilities",
            MappingProxyType(mapped),
        )

    def state(
        self,
        symbol: str,
        spot_exchange: str,
        option_exchange: str,
        field: str,
    ) -> str:
        return self.capabilities[
            (
                symbol.upper(),
                spot_exchange.upper(),
                option_exchange.upper(),
            )
        ][field]


def _common_capabilities() -> dict[str, str]:
    return {
        "spot": "SUPPORTED",
        "provider_timestamp": "SUPPORTED",

        # Task 9 candle authority is intentionally separate:
        # shared WebSocket/cache composition plus closed-candle policy.
        # Do not claim direct provider-live certification here.
        "5m_candles": "UNVERIFIED_LIVE",
        "15m_candles": "UNVERIFIED_LIVE",
        "1h_candles": "UNVERIFIED_LIVE",
        "1d_candles": "UNVERIFIED_LIVE",

        "option_universe": "SUPPORTED",
        "premium_ltp": "SUPPORTED",
        "oi": "SUPPORTED",

        # Native provider OI-change is not Task 9 authority.
        # Task 9 derives signed change from successive same-session
        # live OI snapshots.
        "provider_oi_change": "UNSUPPORTED",
        "derived_oi_change": "DERIVED",

        "volume": "SUPPORTED",
        "bid": "SUPPORTED",
        "ask": "SUPPORTED",

        # Spread is calculated from normalized best ask/bid.
        "spread": "DERIVED",

        "iv": "UNVERIFIED_LIVE",
        "greeks": "UNVERIFIED_LIVE",

        "india_vix_applicability": "OPTIONAL",
    }


def default_provider_capability_registry(
) -> ProviderCapabilityRegistryV1:
    nifty = _common_capabilities()
    nifty.update(
        {
            "iv": "SUPPORTED",
            "greeks": "SUPPORTED",
        }
    )

    sensex = _common_capabilities()
    sensex.update(
        {
            # BFO IV is not certified as an available provider
            # field in the current Task 9 authority.
            "iv": "UNSUPPORTED",

            # Angel option-Greeks capability is NSE/NFO only.
            "greeks": "UNSUPPORTED",
        }
    )

    return ProviderCapabilityRegistryV1(
        {
            (
                "NIFTY",
                "NSE",
                "NFO",
            ): nifty,
            (
                "SENSEX",
                "BSE",
                "BFO",
            ): sensex,
        }
    )


__all__ = (
    "FIELDS",
    "IDENTITIES",
    "STATES",
    "ProviderCapabilityRegistryV1",
    "default_provider_capability_registry",
)
