from __future__ import annotations

from collections.abc import Mapping

from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
    normalize_option_chain,
)


def _canonical_expiry_date(value) -> str:
    text = str(value or "").strip()

    if not text:
        return ""

    prefix = text[:10]

    if len(prefix) == 10 and prefix[4] == "-" and prefix[7] == "-":
        return prefix

    parts = prefix.split("-")

    if (
        len(parts) == 3
        and len(parts[0]) == 2
        and len(parts[1]) == 2
        and len(parts[2]) == 4
    ):
        return parts[2] + "-" + parts[1] + "-" + parts[0]

    return text


class FyersOptionChainProviderV2:
    """
    Native FYERS option-chain reader.

    This deliberately avoids rebuilding an option chain through many
    per-contract depth requests.
    """

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        client,
    ) -> None:
        self._client = client

    def get_option_chain(
        self,
        *,
        underlying_symbol: str,
        strike_count: int,
        expiry_timestamp: int | str | None = None,
        expected_expiry: str | None = None,
    ):
        if (
            not isinstance(
                underlying_symbol,
                str,
            )
            or not underlying_symbol.strip()
        ):
            raise ValueError("underlying_symbol is required")

        if (
            not isinstance(
                strike_count,
                int,
            )
            or strike_count <= 0
        ):
            raise ValueError("strike_count must be positive")

        request: dict[
            str,
            object,
        ] = {
            "symbol": underlying_symbol.strip(),
            "strikecount": strike_count,
        }

        if expiry_timestamp is not None and str(expiry_timestamp).strip():
            request["timestamp"] = expiry_timestamp

        response = self._client.optionchain(data=request)

        if not isinstance(
            response,
            Mapping,
        ):
            raise FyersResponseNormalizationError("invalid FYERS optionchain response")

        data = response.get("data")

        expiry_data = ()

        if isinstance(
            data,
            Mapping,
        ):
            raw_expiry_data = data.get("expiryData")

            if isinstance(
                raw_expiry_data,
                (list, tuple),
            ):
                expiry_data = tuple(
                    dict(item)
                    for item in raw_expiry_data
                    if isinstance(
                        item,
                        Mapping,
                    )
                )

        provider_expiry_date = None
        provider_expiry_timestamp = None

        if expected_expiry is not None:
            target_expiry = _canonical_expiry_date(expected_expiry)

            if not target_expiry:
                raise ValueError("expected_expiry is invalid")

            for item in expiry_data:
                item_date = _canonical_expiry_date(item.get("date"))

                if item_date != target_expiry:
                    continue

                provider_expiry_date = item_date

                provider_expiry_timestamp = item.get("expiry")

                break

            if provider_expiry_timestamp in (
                None,
                "",
            ):
                raise FyersResponseNormalizationError(
                    "FYERS expiryData omitted expected option expiry"
                )

        rows = normalize_option_chain(response)

        return {
            "provider": "FYERS",
            "underlying_symbol": underlying_symbol.strip(),
            "rows": rows,
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "data_only": True,
            "live_execution_eligible": False,
            "expiry_data": expiry_data,
            "provider_expiry_date": provider_expiry_date,
            "provider_expiry_timestamp": provider_expiry_timestamp,
        }
