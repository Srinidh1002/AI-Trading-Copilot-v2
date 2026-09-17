"""FYERS API v3 shared market-data streaming adapter.

Implements ``StreamingMarketDataProviderV2`` without exposing any order
capability. One adapter owns one FYERS DataSocket and multiplexes logical
consumer subscriptions over the socket's physical symbol subscriptions.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol


class FyersStreamingError(RuntimeError):
    """FYERS data streaming failed closed."""


class FyersStreamingConfigurationError(FyersStreamingError):
    """Invalid streaming configuration."""


class FyersStreamingSubscriptionError(FyersStreamingError):
    """Invalid or failed logical subscription."""


class FyersRawDataSocketV2(Protocol):
    def connect(self) -> object:
        ...

    def subscribe(
        self,
        *,
        symbols: Sequence[str],
        data_type: str,
    ) -> object:
        ...

    def unsubscribe(
        self,
        *,
        symbols: Sequence[str],
        data_type: str,
    ) -> object:
        ...

    def close_connection(self) -> object:
        ...


FyersDataSocketFactoryV2 = Callable[..., FyersRawDataSocketV2]


def _default_socket_factory(**kwargs):
    from fyers_apiv3.FyersWebsocket import data_ws

    return data_ws.FyersDataSocket(**kwargs)


def _stream_access_token(
    *,
    access_token: str,
    client_id: str | None,
) -> str:
    token = str(access_token).strip()
    if not token:
        raise FyersStreamingConfigurationError(
            "access_token is required"
        )

    if ":" in token:
        return token

    app_id = (
        str(client_id).strip()
        if client_id is not None
        else ""
    )
    if not app_id:
        raise FyersStreamingConfigurationError(
            "client_id is required for an unqualified access token"
        )
    return f"{app_id}:{token}"


def _install_fyers_ipv4_filter():
    original = socket.getaddrinfo

    def filtered(
        host,
        port,
        family=0,
        type=0,
        proto=0,
        flags=0,
    ):
        if isinstance(host, str) and (
            host.endswith("fyers.in")
            or host.endswith("fyersapi")
        ):
            family = socket.AF_INET
        return original(
            host,
            port,
            family,
            type,
            proto,
            flags,
        )

    socket.getaddrinfo = filtered

    def restore():
        if socket.getaddrinfo is filtered:
            socket.getaddrinfo = original

    return restore


def _coerce_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _provider_datetime(
    value: object,
) -> datetime | None:
    number = _coerce_number(value)
    if number is not None:
        if abs(number) >= 100_000_000_000:
            number /= 1000.0
        try:
            return datetime.fromtimestamp(
                number,
                tz=timezone.utc,
            )
        except (
            OSError,
            OverflowError,
            ValueError,
        ):
            return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(
                text.replace("Z", "+00:00")
            )
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(
            timezone.utc
        )

    return None


def _instrument_metadata(
    instrument: Mapping[str, Any],
) -> tuple[str, dict[str, object]]:
    if not isinstance(instrument, Mapping):
        raise FyersStreamingSubscriptionError(
            "instrument must be a mapping"
        )

    symbol = instrument.get(
        "provider_symbol"
    )
    if (
        not isinstance(symbol, str)
        or not symbol.strip()
    ):
        raise FyersStreamingSubscriptionError(
            "provider_symbol is required"
        )
    symbol = symbol.strip()

    return symbol, {
        "provider_token": instrument.get(
            "provider_token"
        ),
        "canonical_instrument_id": instrument.get(
            "canonical_instrument_id"
        ),
        "market_symbol": instrument.get(
            "market_symbol"
        ),
        "instrument_type": instrument.get(
            "instrument_type"
        ),
    }


class FyersStreamingDataProviderV2:
    """One shared FYERS DataSocket with logical consumer subscriptions."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    DATA_TYPE = "SymbolUpdate"
    MAX_SYMBOLS = 200

    def __init__(
        self,
        *,
        access_token: str,
        log_path: str,
        client_id: str | None = None,
        socket_factory: FyersDataSocketFactoryV2 | None = None,
        reconnect: bool = True,
        ipv4_only: bool = False,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        log_path = str(log_path).strip()
        if not log_path:
            raise FyersStreamingConfigurationError(
                "log_path is required"
            )

        self._access_token = _stream_access_token(
            access_token=access_token,
            client_id=client_id,
        )
        self._log_path = log_path
        self._socket_factory = (
            socket_factory
            or _default_socket_factory
        )
        self._reconnect = bool(reconnect)
        self._ipv4_only = bool(ipv4_only)
        self._now = now or (
            lambda: datetime.now(timezone.utc)
        )

        self._lock = threading.RLock()
        self._connected_event = threading.Event()
        self._socket: FyersRawDataSocketV2 | None = None
        self._thread: threading.Thread | None = None
        self._restore_dns: Callable[[], None] | None = None

        self._closed = False
        self._connected = False
        self._counter = 0
        self._connection_generation = 0
        self._subscriptions: dict[
            str,
            dict[str, object],
        ] = {}
        self._physical_symbols: set[str] = set()
        self._latest_by_symbol: dict[
            str,
            dict[str, object],
        ] = {}

        self._last_message_at: datetime | None = None
        self._last_error: str | None = None
        self._error_count = 0
        self._callback_error_count = 0

    def _desired_symbols_locked(self) -> set[str]:
        desired: set[str] = set()
        for item in self._subscriptions.values():
            desired.update(item["symbols"])
        return desired

    def _ensure_socket_locked(
        self,
    ) -> tuple[FyersRawDataSocketV2, bool]:
        if self._closed:
            raise FyersStreamingError(
                "FYERS_STREAMING_PROVIDER_CLOSED"
            )

        if self._socket is not None:
            return self._socket, False

        if self._ipv4_only and self._restore_dns is None:
            self._restore_dns = (
                _install_fyers_ipv4_filter()
            )

        try:
            self._socket = self._socket_factory(
                access_token=self._access_token,
                log_path=self._log_path,
                litemode=False,
                write_to_file=False,
                reconnect=self._reconnect,
                on_connect=self._on_connect,
                on_close=self._on_close,
                on_error=self._on_error,
                on_message=self._on_message,
            )
        except Exception as exc:
            if self._restore_dns is not None:
                self._restore_dns()
                self._restore_dns = None
            raise FyersStreamingError(
                "FYERS_DATA_SOCKET_CONSTRUCTION_FAILED"
            ) from exc

        self._access_token = ""
        return self._socket, True

    def _start_thread(
        self,
        raw_socket: FyersRawDataSocketV2,
    ) -> None:
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return
            self._thread = threading.Thread(
                target=self._run_socket,
                args=(raw_socket,),
                name="fyers-data-stream-v2",
                daemon=True,
            )
            thread = self._thread
        thread.start()

    def _run_socket(
        self,
        raw_socket: FyersRawDataSocketV2,
    ) -> None:
        try:
            raw_socket.connect()
        except Exception as exc:
            with self._lock:
                self._connected = False
                self._connected_event.clear()
                self._last_error = (
                    f"connect:{type(exc).__name__}"
                )
                self._error_count += 1

    def _subscribe_physical(
        self,
        raw_socket: FyersRawDataSocketV2,
        symbols: set[str],
    ) -> None:
        if not symbols:
            return
        raw_socket.subscribe(
            symbols=tuple(sorted(symbols)),
            data_type=self.DATA_TYPE,
        )

    def _unsubscribe_physical(
        self,
        raw_socket: FyersRawDataSocketV2,
        symbols: set[str],
    ) -> None:
        if not symbols:
            return
        raw_socket.unsubscribe(
            symbols=tuple(sorted(symbols)),
            data_type=self.DATA_TYPE,
        )

    def _on_connect(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connected = True
            self._last_error = None
            self._connection_generation += 1
            raw_socket = self._socket
            desired = self._desired_symbols_locked()
            self._physical_symbols.clear()

        if raw_socket is None:
            return

        try:
            self._subscribe_physical(
                raw_socket,
                desired,
            )
        except Exception as exc:
            with self._lock:
                self._connected = False
                self._connected_event.clear()
                self._last_error = (
                    f"resubscribe:{type(exc).__name__}"
                )
                self._error_count += 1
            return

        with self._lock:
            if self._connected and not self._closed:
                self._physical_symbols = set(
                    desired
                )
                self._connected_event.set()

    def _on_close(self, message=None) -> None:
        del message
        with self._lock:
            self._connected = False
            self._physical_symbols.clear()
            self._connected_event.clear()

    def _on_error(self, message) -> None:
        with self._lock:
            self._connected = False
            self._physical_symbols.clear()
            self._connected_event.clear()
            self._last_error = (
                message[:160]
                if isinstance(message, str)
                else type(message).__name__
            )
            self._error_count += 1

    def _normalize_message(
        self,
        message: Mapping[str, Any],
    ) -> dict[str, object] | None:
        symbol = (
            message.get("symbol")
            or message.get("n")
        )
        if (
            not isinstance(symbol, str)
            or not symbol.strip()
        ):
            return None
        symbol = symbol.strip()

        ltp = _coerce_number(
            message.get(
                "ltp",
                message.get(
                    "last_traded_price",
                    message.get("lp"),
                ),
            )
        )
        if ltp is None or ltp <= 0:
            return None

        received_at = self._now()
        if (
            not isinstance(received_at, datetime)
            or received_at.tzinfo is None
        ):
            raise FyersStreamingConfigurationError(
                "now() must return a timezone-aware datetime"
            )
        received_at = received_at.astimezone(
            timezone.utc
        )

        provider_timestamp = (
            message.get("timestamp")
            or message.get("last_traded_time")
            or message.get("tt")
        )
        provider_dt = _provider_datetime(
            provider_timestamp
        )
        provider_token = (
            message.get("fyToken")
            or message.get("fy_token")
        )

        return {
            "provider": "FYERS",
            "provider_symbol": symbol,
            "provider_token": provider_token,
            "token": provider_token or symbol,
            "token_source": (
                "PROVIDER_TOKEN"
                if provider_token
                else "PROVIDER_SYMBOL"
            ),
            "ltp": float(ltp),
            "ts": provider_dt or received_at,
            "provider_timestamp": provider_timestamp,
            "timestamp_source": (
                "PROVIDER"
                if provider_dt is not None
                else "LOCAL_RECEIPT"
            ),
            "received_at": received_at,
            "raw": dict(message),
            "data_only": True,
            "live_execution_eligible": False,
        }

    def _on_message(self, message) -> None:
        items = (
            message
            if isinstance(message, list)
            else [message]
        )

        for item in items:
            if not isinstance(item, Mapping):
                continue

            try:
                base = self._normalize_message(item)
            except FyersStreamingConfigurationError as exc:
                with self._lock:
                    self._last_error = str(exc)
                    self._error_count += 1
                continue

            if base is None:
                continue

            symbol = base["provider_symbol"]
            callbacks: list[
                tuple[Callable, dict[str, object]]
            ] = []

            with self._lock:
                if self._closed:
                    return
                self._last_message_at = base["received_at"]
                self._latest_by_symbol[symbol] = dict(base)

                for subscription in self._subscriptions.values():
                    metadata = subscription["instruments"].get(
                        symbol
                    )
                    if metadata is not None:
                        callbacks.append(
                            (
                                subscription["callback"],
                                metadata,
                            )
                        )

            for callback, metadata in callbacks:
                record = dict(base)
                instrument_token = metadata.get(
                    "provider_token"
                )
                if (
                    record.get("provider_token") is None
                    and instrument_token is not None
                ):
                    record["provider_token"] = instrument_token
                    record["token"] = str(instrument_token)
                    record["token_source"] = "RESOLVED_INSTRUMENT"

                for key in (
                    "canonical_instrument_id",
                    "market_symbol",
                    "instrument_type",
                ):
                    value = metadata.get(key)
                    if value is not None:
                        record[key] = value

                try:
                    callback(record)
                except Exception:
                    with self._lock:
                        self._callback_error_count += 1

    def subscribe(
        self,
        instruments: Sequence[Mapping[str, Any]],
        callback: Callable[
            [Mapping[str, Any]],
            None,
        ],
    ) -> str:
        if not callable(callback):
            raise TypeError(
                "callback must be callable"
            )
        if isinstance(instruments, (str, bytes)):
            raise FyersStreamingSubscriptionError(
                "instruments must be a sequence of mappings"
            )

        metadata_by_symbol: dict[
            str,
            dict[str, object],
        ] = {}
        for instrument in instruments:
            symbol, metadata = _instrument_metadata(
                instrument
            )
            if symbol in metadata_by_symbol:
                raise FyersStreamingSubscriptionError(
                    "duplicate provider_symbol in subscription"
                )
            metadata_by_symbol[symbol] = metadata

        if not metadata_by_symbol:
            raise FyersStreamingSubscriptionError(
                "at least one instrument is required"
            )

        with self._lock:
            if self._closed:
                raise FyersStreamingError(
                    "FYERS_STREAMING_PROVIDER_CLOSED"
                )

            old_desired = self._desired_symbols_locked()
            prospective = (
                old_desired
                | set(metadata_by_symbol)
            )
            if len(prospective) > self.MAX_SYMBOLS:
                raise FyersStreamingSubscriptionError(
                    "FYERS_STREAM_SYMBOL_LIMIT_EXCEEDED"
                )

            self._counter += 1
            subscription_id = (
                f"fyers-stream-{self._counter}"
            )
            self._subscriptions[subscription_id] = {
                "symbols": frozenset(metadata_by_symbol),
                "instruments": metadata_by_symbol,
                "callback": callback,
            }

            raw_socket, created = self._ensure_socket_locked()
            connected = self._connected
            newly_desired = (
                prospective - old_desired
            )

        if created:
            self._start_thread(raw_socket)
            return subscription_id

        if connected and newly_desired:
            try:
                self._subscribe_physical(
                    raw_socket,
                    newly_desired,
                )
            except Exception as exc:
                with self._lock:
                    self._subscriptions.pop(
                        subscription_id,
                        None,
                    )
                    self._last_error = (
                        f"subscribe:{type(exc).__name__}"
                    )
                    self._error_count += 1
                raise FyersStreamingError(
                    "FYERS_STREAM_SUBSCRIBE_FAILED"
                ) from exc

            with self._lock:
                self._physical_symbols.update(
                    newly_desired
                )

        return subscription_id

    def unsubscribe(
        self,
        subscription_id: str,
    ) -> None:
        subscription_id = str(subscription_id).strip()
        if not subscription_id:
            raise FyersStreamingSubscriptionError(
                "subscription_id is required"
            )

        with self._lock:
            subscription = self._subscriptions.get(
                subscription_id
            )
            if subscription is None:
                raise FyersStreamingSubscriptionError(
                    "FYERS_STREAM_SUBSCRIPTION_UNKNOWN"
                )

            old_desired = self._desired_symbols_locked()
            remaining: set[str] = set()
            for key, item in self._subscriptions.items():
                if key != subscription_id:
                    remaining.update(
                        item["symbols"]
                    )

            remove_physical = (
                old_desired - remaining
            )
            connected = self._connected
            raw_socket = self._socket

        if (
            connected
            and raw_socket is not None
            and remove_physical
        ):
            try:
                self._unsubscribe_physical(
                    raw_socket,
                    remove_physical,
                )
            except Exception as exc:
                with self._lock:
                    self._last_error = (
                        f"unsubscribe:{type(exc).__name__}"
                    )
                    self._error_count += 1
                raise FyersStreamingError(
                    "FYERS_STREAM_UNSUBSCRIBE_FAILED"
                ) from exc

        with self._lock:
            self._subscriptions.pop(
                subscription_id,
                None,
            )
            self._physical_symbols.difference_update(
                remove_physical
            )

    def wait_until_connected(
        self,
        timeout: float,
    ) -> bool:
        if timeout < 0:
            raise ValueError(
                "timeout must be non-negative"
            )
        return self._connected_event.wait(
            timeout
        )

    def get_latest(
        self,
        provider_symbol: str,
    ) -> Mapping[str, object] | None:
        symbol = str(provider_symbol).strip()
        with self._lock:
            record = self._latest_by_symbol.get(
                symbol
            )
            return (
                dict(record)
                if record is not None
                else None
            )

    def is_healthy(
        self,
        stale_seconds: float = 30.0,
    ) -> bool:
        if stale_seconds <= 0:
            raise ValueError(
                "stale_seconds must be positive"
            )

        now = self._now()
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
        ):
            raise FyersStreamingConfigurationError(
                "now() must return a timezone-aware datetime"
            )
        now = now.astimezone(
            timezone.utc
        )

        with self._lock:
            if (
                not self._connected
                or self._last_message_at is None
            ):
                return False
            age = (
                now - self._last_message_at
            ).total_seconds()
            return 0 <= age < stale_seconds

    def snapshot(self) -> Mapping[str, object]:
        with self._lock:
            return {
                "provider": "FYERS",
                "connected": self._connected,
                "closed": self._closed,
                "subscription_count": len(
                    self._subscriptions
                ),
                "desired_symbol_count": len(
                    self._desired_symbols_locked()
                ),
                "physical_symbol_count": len(
                    self._physical_symbols
                ),
                "connection_generation": self._connection_generation,
                "last_message_at": self._last_message_at,
                "last_error": self._last_error,
                "error_count": self._error_count,
                "callback_error_count": self._callback_error_count,
                "data_only": True,
                "order_capability_allowed": False,
                "automatic_fallback_allowed": False,
                "live_execution_eligible": False,
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._connected = False
            self._connected_event.clear()
            self._subscriptions.clear()
            self._physical_symbols.clear()
            raw_socket = self._socket
            thread = self._thread
            restore_dns = self._restore_dns
            self._restore_dns = None

        if raw_socket is not None:
            try:
                raw_socket.close_connection()
            except Exception:
                pass

        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout=2.0)

        if restore_dns is not None:
            restore_dns()

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._connected
