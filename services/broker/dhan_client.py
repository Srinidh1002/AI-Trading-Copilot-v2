"""Secure, lazy wrapper for the official DhanHQ client."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

from services.broker.base_broker import BrokerError


class DhanConfigurationError(BrokerError):
    """Dhan environment configuration is absent or invalid."""


class DhanAuthenticationError(BrokerError):
    """Dhan rejected a read-only authentication check."""


class DhanClientError(BrokerError):
    """The Dhan SDK could not complete a request."""


SdkFactory = Callable[[str, str], Any]


def _official_factory(client_id: str, access_token: str) -> Any:
    try:
        from dhanhq import DhanContext, dhanhq
    except ImportError as exc:
        raise DhanConfigurationError("The dhanhq package is not installed.") from exc
    return dhanhq(DhanContext(client_id, access_token))


class DhanClient:
    """Loads only ``DHAN_CLIENT_ID`` and ``DHAN_ACCESS_TOKEN`` from the env."""

    def __init__(self, sdk_factory: SdkFactory | None = None) -> None:
        self._factory = sdk_factory or _official_factory
        self._sdk: Any | None = None

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            client_id = os.getenv("DHAN_CLIENT_ID", "").strip()
            access_token = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
            missing = [name for name, value in (("DHAN_CLIENT_ID", client_id), ("DHAN_ACCESS_TOKEN", access_token)) if not value]
            if missing:
                raise DhanConfigurationError(f"Missing Dhan environment variable(s): {', '.join(missing)}")
            try:
                self._sdk = self._factory(client_id, access_token)
            except DhanConfigurationError:
                raise
            except Exception as exc:
                raise DhanClientError("Unable to initialise the DhanHQ client.") from exc
        return self._sdk

    def call(self, method_name: str, /, *args: Any, **kwargs: Any) -> Mapping[str, Any]:
        """Call an SDK read method and convert failures to safe exceptions."""

        method = getattr(self.sdk, method_name, None)
        if not callable(method):
            raise DhanClientError(f"DhanHQ SDK does not support {method_name!r}.")
        try:
            response = method(*args, **kwargs)
        except Exception as exc:
            raise DhanClientError(f"Dhan request {method_name!r} failed.") from exc
        if not isinstance(response, Mapping):
            raise DhanClientError(f"Dhan request {method_name!r} returned an invalid response.")
        status = str(response.get("status", "")).lower()
        if status in {"failure", "failed", "error"} or any(key in response for key in ("errorCode", "errorMessage", "errorType")):
            raise DhanAuthenticationError("Dhan rejected the request; verify configured credentials.")
        return response

    def validate_authentication(self) -> bool:
        """Validate credentials through Dhan's read-only fund-limits endpoint."""

        self.call("get_fund_limits")
        return True
