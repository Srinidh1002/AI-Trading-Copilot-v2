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


def _default_rate_limiter():
    """Construct the canonical cross-process FYERS limiter lazily.

    Production entry points put ``src`` on sys.path.  The fallback import keeps
    direct test/tool imports working when only the repository root is present.
    Failure is intentional: a FYERS client without limiter authority must not
    be constructed silently.
    """
    try:
        from rate_limiter import FyersRateLimitCoordinator
    except ImportError:
        from src.rate_limiter import FyersRateLimitCoordinator

    return FyersRateLimitCoordinator(worker_name="FYERS_SDK_FACADE")


def _response_is_rate_limited(response: object) -> bool:
    if not isinstance(response, Mapping):
        return False

    candidates = [response]
    for key in ("error", "Error", "message", "data"):
        value = response.get(key)
        if isinstance(value, Mapping):
            candidates.append(value)

    for value in candidates:
        code = value.get("code")
        try:
            if int(code) == 429:
                return True
        except (TypeError, ValueError):
            pass

        message = str(value.get("message") or "").lower()
        if "request limit" in message or "rate limit" in message:
            return True

    return False


def _exception_is_rate_limited(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "429" in text or "request limit" in text or "rate limit" in text


class FyersDataOnlySdkFacadeV2:
    """Narrow FYERS market-data facade with one global REST request gate.

    The wrapped FYERS SDK object is intentionally not exposed through the
    public API. No order, position, funds, trade-book, order-socket or broker
    submission methods are provided by this facade.

    R18: every synchronous provider call consumes the same cross-process
    limiter budget here, at the lowest common boundary shared by NIFTY,
    SENSEX and all MCX workers.  A provider 429 records a shared cooldown but
    is never retried inside the facade.
    """

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    __slots__ = (
        "_raw_client",
        "_rate_limiter",
    )

    def __init__(
        self,
        raw_client: FyersRawDataClientV2,
        *,
        rate_limiter=None,
    ) -> None:
        if raw_client is None:
            raise ValueError(
                "raw_client is required"
            )

        if rate_limiter is None:
            rate_limiter = _default_rate_limiter()

        if not hasattr(rate_limiter, "wait_if_needed"):
            raise TypeError("rate_limiter must expose wait_if_needed")

        self._raw_client = raw_client
        self._rate_limiter = rate_limiter

    def _call(self, method_name: str, data):
        self._rate_limiter.wait_if_needed(method_name)
        method = getattr(self._raw_client, method_name)

        try:
            response = method(data)
        except Exception as exc:
            if _exception_is_rate_limited(exc) and hasattr(
                self._rate_limiter,
                "record_rate_limit",
            ):
                self._rate_limiter.record_rate_limit(method_name)
            raise

        if _response_is_rate_limited(response) and hasattr(
            self._rate_limiter,
            "record_rate_limit",
        ):
            self._rate_limiter.record_rate_limit(method_name)

        return response

    def quotes(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._call("quotes", data)

    def depth(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._call("depth", data)

    def history(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._call("history", data)

    def optionchain(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._call("optionchain", data)

    def futures_chain(
        self,
        data: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self._call("futures_chain", data)

    def expiry_dates(
        self,
        data: Mapping[str, object],
    ) -> Mapping[str, Any]:
        return self._call("expiry_dates", data)

    def fno_historical_data(
        self,
        data: Mapping[str, object],
    ) -> Mapping[str, Any]:
        return self._call("fno_historical_data", data)


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
    rate_limiter=None,
) -> FyersDataOnlySdkFacadeV2:
    """Construct a synchronous FYERS data-only facade.

    Credentials are explicit arguments. This function never reads .env or
    process environment variables.

    ``model_factory`` and ``rate_limiter`` can be injected for tests so no
    FYERS package, network capability or live limiter state is required.
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
        raw_client,
        rate_limiter=rate_limiter,
    )
