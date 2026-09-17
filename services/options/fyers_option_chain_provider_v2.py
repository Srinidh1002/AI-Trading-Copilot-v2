from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.broker.fyers_response_normalizer_v2 import (
    FyersResponseNormalizationError,
    normalize_option_chain,
)


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
    ):
        if (
            not isinstance(
                underlying_symbol,
                str,
            )
            or not underlying_symbol.strip()
        ):
            raise ValueError(
                "underlying_symbol is required"
            )

        if (
            not isinstance(
                strike_count,
                int,
            )
            or strike_count <= 0
        ):
            raise ValueError(
                "strike_count must be positive"
            )

        request: dict[
            str,
            object,
        ] = {
            "symbol":
                underlying_symbol.strip(),

            "strikecount":
                strike_count,

            "timestamp":
                (
                    ""
                    if expiry_timestamp
                    is None
                    else expiry_timestamp
                ),
        }

        response = (
            self._client.optionchain(
                data=request
            )
        )

        if not isinstance(
            response,
            Mapping,
        ):
            raise FyersResponseNormalizationError(
                "invalid FYERS optionchain response"
            )

        rows = normalize_option_chain(
            response
        )

        return {
            "provider":
                "FYERS",

            "underlying_symbol":
                underlying_symbol.strip(),

            "rows":
                rows,

            "request_count":
                1,

            "per_contract_depth_requests":
                0,

            "data_only":
                True,

            "live_execution_eligible":
                False,
        }
