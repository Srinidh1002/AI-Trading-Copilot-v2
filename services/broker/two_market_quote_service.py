"""Canonical batched NIFTY and SENSEX FULL quote acquisition.

This module performs exactly one read-only Angel One market-data request
for the two certified Indian index identities.

No broker order submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


NIFTY_MARKET = "NIFTY"
NIFTY_EXCHANGE = "NSE"
NIFTY_SYMBOLTOKEN = "99926000"

SENSEX_MARKET = "SENSEX"
SENSEX_EXCHANGE = "BSE"
SENSEX_SYMBOLTOKEN = "99919000"

CANONICAL_MARKET_ORDER = (
    NIFTY_MARKET,
    SENSEX_MARKET,
)

CANONICAL_EXCHANGE_TOKENS = {
    NIFTY_EXCHANGE: [
        NIFTY_SYMBOLTOKEN,
    ],
    SENSEX_EXCHANGE: [
        SENSEX_SYMBOLTOKEN,
    ],
}


class MarketDataClient(Protocol):
    """Read-only client contract used by this service."""

    def get_market_data(
        self,
        mode: str,
        exchange_tokens: Mapping[
            str,
            list[str],
        ],
    ) -> Mapping[str, object]:
        """Return an Angel One market-data envelope."""


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalIndexFullQuote:
    """Validated FULL quote for one canonical index."""

    market: str
    exchange: str
    symboltoken: str
    tradingsymbol: str
    ltp: float
    payload: Mapping[str, object]


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalTwoMarketFullQuotes:
    """Deterministically ordered NIFTY and SENSEX quotes."""

    nifty: CanonicalIndexFullQuote
    sensex: CanonicalIndexFullQuote

    def ordered(
        self,
    ) -> tuple[
        CanonicalIndexFullQuote,
        CanonicalIndexFullQuote,
    ]:
        return (
            self.nifty,
            self.sensex,
        )

    def by_market(
        self,
    ) -> Mapping[
        str,
        CanonicalIndexFullQuote,
    ]:
        return {
            NIFTY_MARKET: self.nifty,
            SENSEX_MARKET: self.sensex,
        }


_EXPECTED_IDENTITIES = {
    (
        NIFTY_EXCHANGE,
        NIFTY_SYMBOLTOKEN,
    ): NIFTY_MARKET,
    (
        SENSEX_EXCHANGE,
        SENSEX_SYMBOLTOKEN,
    ): SENSEX_MARKET,
}


def _mapping(
    value: object,
    *,
    name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(
            f"Canonical two-market quote response "
            f"contains invalid {name}."
        )

    return value


def _list(
    value: object,
    *,
    name: str,
) -> list[object]:
    if not isinstance(value, list):
        raise RuntimeError(
            f"Canonical two-market quote response "
            f"contains invalid {name}."
        )

    return value


def _identity(
    item: Mapping[str, object],
) -> tuple[str, str]:
    exchange = str(
        item.get(
            "exchange",
            "",
        )
    ).strip().upper()

    symboltoken = str(
        item.get(
            "symbolToken",
            item.get(
                "symboltoken",
                "",
            ),
        )
    ).strip()

    return (
        exchange,
        symboltoken,
    )


def _positive_float(
    value: object,
    *,
    market: str,
) -> float:
    try:
        result = float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise RuntimeError(
            f"{market} FULL quote contains "
            "an invalid LTP."
        ) from exc

    if result <= 0:
        raise RuntimeError(
            f"{market} FULL quote contains "
            "a non-positive LTP."
        )

    return result


def _unfetched_reason(
    item: Mapping[str, object],
) -> str:
    error_code = str(
        item.get(
            "errorCode",
            item.get(
                "errorcode",
                "",
            ),
        )
    ).strip()

    message = str(
        item.get(
            "message",
            "Provider did not return the requested quote.",
        )
    ).strip()

    if error_code and message:
        return f"{error_code} - {message}"

    return (
        error_code
        or message
        or "Unknown provider failure"
    )


def _build_quote(
    *,
    market: str,
    exchange: str,
    symboltoken: str,
    item: Mapping[str, object],
) -> CanonicalIndexFullQuote:
    tradingsymbol = str(
        item.get(
            "tradingSymbol",
            item.get(
                "tradingsymbol",
                market,
            ),
        )
    ).strip()

    if not tradingsymbol:
        tradingsymbol = market

    return CanonicalIndexFullQuote(
        market=market,
        exchange=exchange,
        symboltoken=symboltoken,
        tradingsymbol=tradingsymbol,
        ltp=_positive_float(
            item.get("ltp"),
            market=market,
        ),
        payload=dict(item),
    )


def fetch_canonical_two_market_full_quotes(
    market_client: MarketDataClient,
) -> CanonicalTwoMarketFullQuotes:
    """Fetch and validate NIFTY and SENSEX in one FULL request."""

    if not callable(
        getattr(
            market_client,
            "get_market_data",
            None,
        )
    ):
        raise TypeError(
            "market_client must expose "
            "get_market_data()."
        )

    response = market_client.get_market_data(
        "FULL",
        {
            exchange: list(tokens)
            for exchange, tokens
            in CANONICAL_EXCHANGE_TOKENS.items()
        },
    )

    envelope = _mapping(
        response,
        name="response envelope",
    )

    data = _mapping(
        envelope.get("data"),
        name="data",
    )

    fetched = _list(
        data.get("fetched"),
        name="fetched list",
    )

    unfetched = _list(
        data.get("unfetched"),
        name="unfetched list",
    )

    for raw_item in unfetched:
        item = _mapping(
            raw_item,
            name="unfetched item",
        )

        identity = _identity(item)

        if identity in _EXPECTED_IDENTITIES:
            market = _EXPECTED_IDENTITIES[
                identity
            ]

            raise RuntimeError(
                f"{market} FULL quote was unfetched: "
                f"{_unfetched_reason(item)}"
            )

        raise RuntimeError(
            "Canonical two-market FULL response "
            "contains an unexpected unfetched identity."
        )

    matches: dict[
        tuple[str, str],
        list[Mapping[str, object]],
    ] = {
        identity: []
        for identity in _EXPECTED_IDENTITIES
    }

    for raw_item in fetched:
        item = _mapping(
            raw_item,
            name="fetched item",
        )

        identity = _identity(item)

        if identity not in _EXPECTED_IDENTITIES:
            raise RuntimeError(
                "Canonical two-market FULL response "
                "contains an unexpected fetched identity."
            )

        matches[identity].append(item)

    for identity, items in matches.items():
        market = _EXPECTED_IDENTITIES[
            identity
        ]

        if len(items) != 1:
            raise RuntimeError(
                f"Canonical two-market FULL response "
                f"must contain exactly one {market} quote."
            )

    nifty_item = matches[
        (
            NIFTY_EXCHANGE,
            NIFTY_SYMBOLTOKEN,
        )
    ][0]

    sensex_item = matches[
        (
            SENSEX_EXCHANGE,
            SENSEX_SYMBOLTOKEN,
        )
    ][0]

    return CanonicalTwoMarketFullQuotes(
        nifty=_build_quote(
            market=NIFTY_MARKET,
            exchange=NIFTY_EXCHANGE,
            symboltoken=NIFTY_SYMBOLTOKEN,
            item=nifty_item,
        ),
        sensex=_build_quote(
            market=SENSEX_MARKET,
            exchange=SENSEX_EXCHANGE,
            symboltoken=SENSEX_SYMBOLTOKEN,
            item=sensex_item,
        ),
    )


def fetch_shared_canonical_two_market_full_quotes():
    """Fetch canonical two-market FULL quotes via the shared client."""

    from services.broker.shared_client import (
        get_market_client,
    )

    return fetch_canonical_two_market_full_quotes(
        get_market_client()
    )
