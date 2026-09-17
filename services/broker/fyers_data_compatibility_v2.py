from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
    normalize_full_market_data,
    normalize_history,
    normalize_ltp_data,
)


class FyersDataClientV2(Protocol):
    """Injected FYERS market-data client boundary."""

    def quotes(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...

    def history(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...

    def depth(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...


ProviderSymbolResolverV2 = Callable[
    [str, str | None, str],
    str,
]


_INTERVAL_MAP = {
    "ONE_MINUTE": "1",
    "THREE_MINUTE": "3",
    "FIVE_MINUTE": "5",
    "TEN_MINUTE": "10",
    "FIFTEEN_MINUTE": "15",
    "THIRTY_MINUTE": "30",
    "ONE_HOUR": "60",
    "ONE_DAY": "D",
}


class FyersDataOnlyCompatibilityV2:
    """
    Data-only FYERS compatibility boundary for the current Angel-shaped readers.

    This class does not:
    - create a FYERS SDK client;
    - read credentials;
    - authenticate;
    - create sockets;
    - expose order methods;
    - perform provider fallback.

    A market-data client and symbol resolver must be injected explicitly.
    """

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        *,
        client: FyersDataClientV2,
        symbol_resolver: ProviderSymbolResolverV2,
    ) -> None:
        if client is None:
            raise ValueError(
                "client is required"
            )

        if not callable(
            symbol_resolver
        ):
            raise ValueError(
                "symbol_resolver must be callable"
            )

        self._client = client
        self._symbol_resolver = (
            symbol_resolver
        )

    def _resolve(
        self,
        *,
        exchange: str,
        tradingsymbol: str | None,
        symboltoken: str,
    ) -> str:
        provider_symbol = (
            self._symbol_resolver(
                str(exchange),
                (
                    str(tradingsymbol)
                    if tradingsymbol
                    is not None
                    else None
                ),
                str(symboltoken),
            )
        )

        if (
            not isinstance(
                provider_symbol,
                str,
            )
            or not provider_symbol.strip()
        ):
            raise FyersResponseNormalizationError(
                "provider symbol resolution failed"
            )

        return provider_symbol.strip()

    @staticmethod
    def _parse_ist(
        value: object,
        *,
        field: str,
    ) -> datetime:
        if not isinstance(
            value,
            str,
        ):
            raise FyersResponseNormalizationError(
                f"{field} must be a string"
            )

        text = value.strip()

        formats = (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
        )

        parsed = None

        for fmt in formats:
            try:
                parsed = datetime.strptime(
                    text,
                    fmt,
                )
                break
            except ValueError:
                continue

        if parsed is None:
            raise FyersResponseNormalizationError(
                f"{field} has unsupported datetime format"
            )

        return parsed.replace(
            tzinfo=ZoneInfo(
                "Asia/Kolkata"
            )
        )

    def ltpData(
        self,
        exchange: str,
        tradingsymbol: str,
        symboltoken: str,
    ) -> dict[str, object]:
        provider_symbol = self._resolve(
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            symboltoken=symboltoken,
        )

        response = self._client.quotes(
            {
                "symbols":
                    provider_symbol
            }
        )

        return normalize_ltp_data(
            response,
            provider_symbol=provider_symbol,
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            symboltoken=str(
                symboltoken
            ),
        )

    def getCandleData(
        self,
        params: Mapping[str, object],
    ) -> dict[str, object]:
        exchange = params.get(
            "exchange"
        )

        symboltoken = params.get(
            "symboltoken"
        )

        interval = params.get(
            "interval"
        )

        if (
            not isinstance(
                exchange,
                str,
            )
            or not isinstance(
                symboltoken,
                (str, int),
            )
            or not isinstance(
                interval,
                str,
            )
        ):
            raise FyersResponseNormalizationError(
                "invalid candle request"
            )

        resolution = _INTERVAL_MAP.get(
            interval.upper()
        )

        if resolution is None:
            raise FyersResponseNormalizationError(
                "unsupported candle interval"
            )

        provider_symbol = self._resolve(
            exchange=exchange,
            tradingsymbol=None,
            symboltoken=str(
                symboltoken
            ),
        )

        start = self._parse_ist(
            params.get(
                "fromdate"
            ),
            field="fromdate",
        )

        end = self._parse_ist(
            params.get(
                "todate"
            ),
            field="todate",
        )

        if end <= start:
            raise FyersResponseNormalizationError(
                "todate must be after fromdate"
            )

        response = self._client.history(
            {
                "symbol":
                    provider_symbol,

                "resolution":
                    resolution,

                "date_format":
                    "0",

                "range_from":
                    int(
                        start.timestamp()
                    ),

                "range_to":
                    int(
                        end.timestamp()
                    ),

                "cont_flag":
                    "0",
            }
        )

        return normalize_history(
            response
        )

    def getMarketData(
        self,
        mode: str,
        exchange_tokens: Mapping[
            str,
            Sequence[str],
        ],
    ) -> dict[str, object]:
        if str(mode).upper() != "FULL":
            raise FyersResponseNormalizationError(
                "only FULL market data is supported"
            )

        if not isinstance(
            exchange_tokens,
            Mapping,
        ):
            raise FyersResponseNormalizationError(
                "exchange_tokens must be a mapping"
            )

        fetched: list[
            dict[str, object]
        ] = []

        for exchange, tokens in exchange_tokens.items():
            if (
                not isinstance(
                    exchange,
                    str,
                )
                or not isinstance(
                    tokens,
                    Sequence,
                )
                or isinstance(
                    tokens,
                    (str, bytes),
                )
            ):
                raise FyersResponseNormalizationError(
                    "invalid FULL market-data request"
                )

            for raw_token in tokens:
                token = str(
                    raw_token
                )

                provider_symbol = self._resolve(
                    exchange=exchange,
                    tradingsymbol=None,
                    symboltoken=token,
                )

                response = self._client.depth(
                    {
                        "symbol":
                            provider_symbol,

                        "ohlcv_flag":
                            "1",
                    }
                )

                normalized = (
                    normalize_full_market_data(
                        response,
                        provider_symbol=provider_symbol,
                        symboltoken=token,
                    )
                )

                rows = (
                    normalized
                    .get(
                        "data",
                        {},
                    )
                    .get(
                        "fetched",
                        [],
                    )
                )

                if (
                    not isinstance(
                        rows,
                        list,
                    )
                    or len(rows) != 1
                    or not isinstance(
                        rows[0],
                        dict,
                    )
                ):
                    raise FyersResponseNormalizationError(
                        "normalized FULL response is invalid"
                    )

                fetched.append(
                    rows[0]
                )

        if not fetched:
            raise FyersResponseNormalizationError(
                "FULL market-data request resolved no instruments"
            )

        return {
            "status": True,
            "data": {
                "fetched":
                    fetched
            },
        }
