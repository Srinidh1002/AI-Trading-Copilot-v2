from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any


class FyersProviderAdapterError(RuntimeError):
    """FYERS provider adapter failed closed."""


def _provider_symbol(
    instrument: Mapping[str, Any],
) -> str:
    value = instrument.get(
        "provider_symbol"
    )

    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise FyersProviderAdapterError(
            "provider_symbol is required"
        )

    return value.strip()


def _resolution(
    interval: str,
) -> str:
    mapping = {
        "ONE_MINUTE": "1",
        "THREE_MINUTE": "3",
        "FIVE_MINUTE": "5",
        "TEN_MINUTE": "10",
        "FIFTEEN_MINUTE": "15",
        "THIRTY_MINUTE": "30",
        "ONE_HOUR": "60",
        "ONE_DAY": "D",
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "10m": "10",
        "15m": "15",
        "30m": "30",
        "60m": "60",
        "1d": "D",
    }

    result = mapping.get(
        str(interval)
    )

    if result is None:
        raise FyersProviderAdapterError(
            f"unsupported interval: {interval}"
        )

    return result


class FyersHistoricalDataProviderV2:
    def __init__(self, client) -> None:
        self._client = client

    def get_candles(
        self,
        instrument,
        *,
        interval,
        start,
        end,
    ):
        symbol = _provider_symbol(
            instrument
        )

        if not isinstance(
            start,
            datetime,
        ) or not isinstance(
            end,
            datetime,
        ):
            raise FyersProviderAdapterError(
                "start/end must be datetime"
            )

        if end <= start:
            raise FyersProviderAdapterError(
                "end must be after start"
            )

        response = self._client.history(
            {
                "symbol": symbol,
                "resolution": _resolution(
                    interval
                ),
                "date_format": "0",
                "range_from": int(
                    start.timestamp()
                ),
                "range_to": int(
                    end.timestamp()
                ),
                "cont_flag": "0",
            }
        )

        if (
            not isinstance(response, Mapping)
            or response.get("s") != "ok"
        ):
            raise FyersProviderAdapterError(
                "FYERS history failed"
            )

        candles = response.get(
            "candles"
        )

        if not isinstance(
            candles,
            list,
        ):
            raise FyersProviderAdapterError(
                "FYERS candles missing"
            )

        result = []

        for row in candles:
            if (
                not isinstance(row, list)
                or len(row) < 6
            ):
                raise FyersProviderAdapterError(
                    "invalid FYERS candle"
                )

            item = {
                "provider": "FYERS",
                "provider_symbol": symbol,
                "timestamp": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
                "interval": interval,
            }

            if len(row) >= 7:
                item["open_interest"] = (
                    row[6]
                )

            result.append(item)

        return tuple(result)


class FyersQuoteDepthProviderV2:
    def __init__(self, client) -> None:
        self._client = client

    def get_quote(self, instrument):
        symbol = _provider_symbol(
            instrument
        )

        response = self._client.quotes(
            {
                "symbols": symbol
            }
        )

        if (
            not isinstance(response, Mapping)
            or response.get("s") != "ok"
        ):
            raise FyersProviderAdapterError(
                "FYERS quote failed"
            )

        rows = response.get("d")

        if not isinstance(rows, list):
            raise FyersProviderAdapterError(
                "FYERS quote rows missing"
            )

        matches = []

        for row in rows:
            if not isinstance(
                row,
                Mapping,
            ):
                continue

            payload = row.get(
                "v",
                row,
            )

            if not isinstance(
                payload,
                Mapping,
            ):
                continue

            if (
                row.get("n") == symbol
                or payload.get("symbol")
                == symbol
            ):
                matches.append(
                    payload
                )

        if len(matches) != 1:
            raise FyersProviderAdapterError(
                "FYERS quote identity ambiguous"
            )

        payload = matches[0]

        lp = payload.get("lp")

        if (
            not isinstance(
                lp,
                (int, float),
            )
            or lp <= 0
        ):
            raise FyersProviderAdapterError(
                "FYERS quote price invalid"
            )

        return {
            "provider": "FYERS",
            "provider_symbol": symbol,
            "last_price": float(lp),
            "bid_price": payload.get(
                "bid"
            ),
            "ask_price": payload.get(
                "ask"
            ),
            "volume": payload.get(
                "volume"
            ),
            "provider_token": payload.get(
                "fyToken"
            ),
            "provider_timestamp": payload.get(
                "tt"
            ),
            "data_only": True,
            "live_execution_eligible": False,
        }

    def get_depth(self, instrument):
        symbol = _provider_symbol(
            instrument
        )

        response = self._client.depth(
            {
                "symbol": symbol,
                "ohlcv_flag": "1",
            }
        )

        if (
            not isinstance(response, Mapping)
            or response.get("s") != "ok"
        ):
            raise FyersProviderAdapterError(
                "FYERS depth failed"
            )

        root = response.get("d")

        if not isinstance(
            root,
            Mapping,
        ):
            raise FyersProviderAdapterError(
                "FYERS depth payload missing"
            )

        payload = root.get(
            symbol
        )

        if not isinstance(
            payload,
            Mapping,
        ):
            raise FyersProviderAdapterError(
                "FYERS depth symbol missing"
            )

        return {
            "provider": "FYERS",
            "provider_symbol": symbol,
            "last_price": payload.get(
                "ltp"
            ),
            "bids": tuple(
                payload.get("bids")
                or ()
            ),
            "asks": tuple(
                payload.get("ask")
                or payload.get("asks")
                or ()
            ),
            "open_interest": payload.get(
                "oi"
            ),
            "volume": payload.get(
                "volume",
                payload.get("v"),
            ),
            "open": payload.get("o"),
            "high": payload.get("h"),
            "low": payload.get("l"),
            "close": payload.get("c"),
            "expiry": payload.get(
                "expiry"
            ),
            "tick_size": payload.get(
                "tick_Size"
            ),
            "data_only": True,
            "live_execution_eligible": False,
        }


class InjectedFyersInstrumentResolverV2:
    """
    F7 composition seam only.

    Production five-market identity resolution is F8.
    """

    def __init__(
        self,
        resolver: Callable[..., Mapping[str, Any]],
    ) -> None:
        if not callable(resolver):
            raise ValueError(
                "resolver must be callable"
            )

        self._resolver = resolver

    def resolve(
        self,
        *,
        market_symbol,
        instrument_type,
        as_of=None,
        expiry=None,
        strike=None,
        option_type=None,
    ):
        result = self._resolver(
            market_symbol=market_symbol,
            instrument_type=instrument_type,
            as_of=as_of,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
        )

        if not isinstance(
            result,
            Mapping,
        ):
            raise FyersProviderAdapterError(
                "resolver returned invalid result"
            )

        if not result.get(
            "provider_symbol"
        ):
            raise FyersProviderAdapterError(
                "resolver omitted provider_symbol"
            )

        return result


class FyersRequestControllerV2:
    """
    Minimal deterministic request-controller contract.

    Provider-specific rate-budget sophistication can be extended later without
    changing the V2 orchestration API.
    """

    def wait_for_slot(
        self,
        request_type,
        attempt,
    ):
        return 0.0

    def record_rate_limit(
        self,
        request_type,
        retry_number,
        backoff_multiplier,
    ):
        return 0.0

    def record_success(
        self,
        request_type,
    ):
        return None


class FyersStreamingUnavailableV2:
    """
    Fail-closed F7 placeholder.

    Real FYERS streaming is implemented in its dedicated later phase.
    """

    def subscribe(
        self,
        instruments,
        callback,
    ):
        raise FyersProviderAdapterError(
            "FYERS streaming runtime not installed"
        )

    def unsubscribe(
        self,
        subscription_id,
    ):
        return None

    def close(self):
        return None
