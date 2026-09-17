from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol


class FyersRawDataClientV2(Protocol):
    def quotes(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...

    def depth(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...

    def history(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...

    def optionchain(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...

    def futures_chain(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        ...

    def expiry_dates(
        self,
        data: Mapping[str, object],
    ) -> Mapping[str, Any]:
        ...

    def fno_historical_data(
        self,
        data: Mapping[str, object],
    ) -> Mapping[str, Any]:
        ...


FyersModelFactoryV2 = Callable[..., FyersRawDataClientV2]


class FyersDataOnlySdkFacadeV2:
    """
    Narrow FYERS market-data facade.

    The wrapped FYERS SDK object is intentionally not exposed through the
    public API. No order, position, funds, trade-book, order-socket or broker
    submission methods are provided by this facade.
    """

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    __slots__ = (
        "_raw_client",
    )

    def __init__(
        self,
        raw_client: FyersRawDataClientV2,
    ) -> None:
        if raw_client is None:
            raise ValueError(
                "raw_client is required"
            )

        self._raw_client = (
            raw_client
        )

    def quotes(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._raw_client.quotes(
            data
        )

    def depth(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._raw_client.depth(
            data
        )

    def history(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._raw_client.history(
            data
        )

    def optionchain(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._raw_client.optionchain(
            data
        )

    def futures_chain(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._raw_client.futures_chain(
            data
        )

    def expiry_dates(
        self,
        data: Mapping[str, object],
    ) -> Mapping[str, Any]:
        return self._raw_client.expiry_dates(
            data
        )

    def fno_historical_data(
        self,
        data: Mapping[str, object],
    ) -> Mapping[str, Any]:
        return self._raw_client.fno_historical_data(
            data
        )


def _raw_access_token(
    *,
    client_id: str,
    access_token: str,
) -> str:
    client_id = str(
        client_id
    ).strip()

    access_token = str(
        access_token
    ).strip()

    if not client_id:
        raise ValueError(
            "client_id is required"
        )

    if not access_token:
        raise ValueError(
            "access_token is required"
        )

    prefix = (
        client_id
        + ":"
    )

    if access_token.startswith(
        prefix
    ):
        return access_token[
            len(prefix):
        ]

    return access_token


def build_fyers_data_client_v2(
    *,
    client_id: str,
    access_token: str,
    log_path: str,
    model_factory: FyersModelFactoryV2 | None = None,
) -> FyersDataOnlySdkFacadeV2:
    """
    Construct a synchronous FYERS data-only facade.

    Credentials are explicit arguments. This function never reads .env or
    process environment variables.

    A model_factory can be injected for tests so no FYERS package or network
    capability is required by unit tests.
    """

    client_id = str(
        client_id
    ).strip()

    log_path = str(
        log_path
    ).strip()

    if not log_path:
        raise ValueError(
            "log_path is required"
        )

    raw_token = _raw_access_token(
        client_id=client_id,
        access_token=access_token,
    )

    if model_factory is None:
        from fyers_apiv3 import fyersModel

        model_factory = (
            fyersModel.FyersModel
        )

    raw_client = model_factory(
        client_id=client_id,
        token=raw_token,
        is_async=False,
        log_path=log_path,
    )

    return FyersDataOnlySdkFacadeV2(
        raw_client
    )
