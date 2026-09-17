"""
Resilient Angel One SmartAPI market-data client.

Handles:
- Authentication using TOTP
- Automatic retry for temporary API/network failures
- Exponential retry backoff
- Automatic re-authentication when the session expires
- Live market data requests
- Historical candle data requests
- Option Greeks requests
- Response validation

Read-only.
No orders are placed from this client.
"""

import logging
import re
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pyotp
from utils.debug import debug_print
from SmartApi import SmartConnect

from config import (
    ANGEL_API_KEY,
    ANGEL_CLIENT_ID,
    ANGEL_PIN,
    ANGEL_TOTP_SECRET,
)
from services.broker.market_data_control import (
    BrokerMarketDataRequestError,
    MarketDataRequestController,
    configured_value,
)


LOGGER = logging.getLogger(__name__)
_TRADING_TIMEZONE = ZoneInfo("Asia/Kolkata")
_SECRET_VALUE = re.compile(r"(?i)((?:x-privatekey|api[_ -]?key|authorization|jwt|refresh[_ -]?token|feed[_ -]?token|pin|totp|cookie|session)[\"']?\s*[:=]\s*[\"']?)([^,\s}\]'\"]+)")


def _safe_provider_reason(value):
    """Retain a bounded operational reason without credentials or headers."""
    raw = str(value)
    if _SECRET_VALUE.search(raw):
        return "REDACTED_PROVIDER_ERROR"
    text = raw
    return " ".join(text.split())[:200]


def _current_trading_date() -> date:
    """Return Angel's local session date without retaining credentials."""
    return datetime.now(_TRADING_TIMEZONE).date()


def _suppress_smartapi_logs():
    """Prevent SmartAPI SDK loggers from exposing request headers."""
    logger_names = {
        "SmartApi",
        "smartapi",
        "smartapi-python",
        "smartConnect",
        "SmartApi.smartConnect",
        "logzero_default",
    }

    logger_names.update(
        name
        for name in logging.root.manager.loggerDict
        if (
            "smartapi" in name.lower()
            or "smartconnect" in name.lower()
        )
    )

    for name in logger_names:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.disabled = True
        logger.propagate = False
        logger.setLevel(logging.CRITICAL + 1)

class AngelMarketDataClient:
    """
    Resilient read-only client for
    Angel One SmartAPI market data.
    """

    def __init__(
        self,
        max_retries=3,
        retry_delay_seconds=1.0,
        retry_backoff_multiplier=2.0,
        min_request_interval_seconds=None,
        historical_request_interval_seconds=None,
        cache_ttl_seconds=None,
        rate_limit_cooldown_seconds=None,
        max_rate_limit_retries=None,
        request_controller=None,
        current_date=None,
        
    ):
        if not ANGEL_API_KEY:
            raise ValueError(
                "ANGEL_API_KEY is missing."
            )

        if max_retries < 1:
            raise ValueError(
                "max_retries must be at least 1."
            )

        if retry_delay_seconds < 0:
            raise ValueError(
                "retry_delay_seconds cannot be negative."
            )

        if retry_backoff_multiplier < 1:
            raise ValueError(
                "retry_backoff_multiplier must "
                "be at least 1."
            )

        if current_date is not None and not callable(current_date):
            raise TypeError("current_date must be callable.")

        _suppress_smartapi_logs()
        self.api = SmartConnect(
            api_key=ANGEL_API_KEY
        )
        _suppress_smartapi_logs()
        self.max_retries = (
            max_retries
        )

        self.retry_delay_seconds = (
            retry_delay_seconds
        )

        self.retry_backoff_multiplier = (
            retry_backoff_multiplier
        )

        self.max_rate_limit_retries = configured_value(
            "ANGEL_MARKET_DATA_MAX_RATE_LIMIT_RETRIES",
            2,
            int,
            max_rate_limit_retries,
        )

        self.request_controller = (
            request_controller
            if request_controller is not None
            else MarketDataRequestController(
                min_request_interval_seconds=(
                    min_request_interval_seconds
                ),
                historical_request_interval_seconds=(
                    historical_request_interval_seconds
                ),
                cache_ttl_seconds=cache_ttl_seconds,
                rate_limit_cooldown_seconds=(
                    rate_limit_cooldown_seconds
                ),

            )
            
        )
        debug_print(f"AngelMarketDataClient created: {id(self)}")
        self.authenticated = False

        self.session = None
        self._current_date = current_date or _current_trading_date
        self._authenticated_on = None

    # ---------------------------------
    # AUTHENTICATION
    # ---------------------------------

    def login(
            
        self,
        force=False,
    ):
        debug_print(f"LOGIN -> instance={id(self)} authenticated={self.authenticated}")
        """
        Authenticate with Angel One using
        Client ID, PIN and TOTP.

        When force=True, create a fresh session.
        """

        if self.authenticated and not force:
            # Sessions are valid only through local midnight.  Test doubles
            # created before this guard have no authenticated-date metadata;
            # retain their legacy injected-client behaviour rather than
            # guessing a date for them.
            if (
                self._authenticated_on is None
                or self._authenticated_on == self._current_date()
            ):
                return self.session
            self._reset_session()

        if not ANGEL_CLIENT_ID:
            raise ValueError(
                "ANGEL_CLIENT_ID is missing."
            )

        if not ANGEL_PIN:
            raise ValueError(
                "ANGEL_PIN is missing."
            )

        if not ANGEL_TOTP_SECRET:
            raise ValueError(
                "ANGEL_TOTP_SECRET is missing."
            )

        if force:
            self._reset_session()

        totp = pyotp.TOTP(
            ANGEL_TOTP_SECRET
        ).now()

        LOGGER.info(
            "broker_auth action=generate_session monotonic=%.6f force=%s",
            time.monotonic(),
            bool(force),
        )

        try:
            self.request_controller.wait_for_slot(
                "authentication",
                1,
            )
            response = (
                self.api.generateSession(
                    ANGEL_CLIENT_ID,
                    ANGEL_PIN,
                    totp,
                )
            )

            self.request_controller.mark_request_complete(
                "authentication"
            )

        except Exception as exc:
            self._reset_session()

            raise RuntimeError("Angel One login request failed: " + _safe_provider_reason(exc)) from exc
        if self._is_rate_limit_error(
            response=response,
        ):
            self.request_controller.record_rate_limit(
                "authentication",
                1,
                self.retry_backoff_multiplier,
            )

        try:
            validated_response = (
                self._validate_response(
                    response,
                    "login",
                )
            )

            session_data = (
                validated_response.get(
                    "data"
                )
            )

            if not isinstance(
                session_data,
                dict,
            ):
                raise RuntimeError(
                    "Angel One login returned "
                    "invalid session data."
                )

            required_tokens = (
                "jwtToken",
                "refreshToken",
                "feedToken",
            )

            missing_tokens = tuple(
                name
                for name in required_tokens
                if (
                    not isinstance(
                        session_data.get(name),
                        str,
                    )
                    or not session_data[
                        name
                    ].strip()
                )
            )

            if missing_tokens:
                raise RuntimeError(
                    "Angel One login returned "
                    "incomplete authentication data."
                )

        except Exception:
            self._reset_session()
            raise

        self.authenticated = True
        self.session = validated_response
        self._authenticated_on = self._current_date()

        return validated_response

    # ---------------------------------
    # SESSION HELPERS
    # ---------------------------------

    def _ensure_authenticated(
        self,
    ):
        """
        Ensure an authenticated session exists.
        """

        if (
            self.authenticated
            and self._authenticated_on is not None
            and self._authenticated_on != self._current_date()
        ):
            self._reset_session()

        if not self.authenticated:
            self.login()

    def _reset_session(
        self,
    ):
        """
        Mark the current session as invalid.

        A new login will occur before the
        next protected API request.
        """

        self.authenticated = False

        self.session = None
        self._authenticated_on = None

    # ---------------------------------
    # ERROR CLASSIFICATION
    # ---------------------------------

    @staticmethod
    def _is_rate_limit_error(
        response=None,
        exception=None,
    ):
        """Detect documented Angel One rate-limit failures."""

        from services.broker.angel_provider_failure import (
            classify_angel_provider_failure,
            is_angel_rate_limit_failure,
        )

        classification = classify_angel_provider_failure(
            response=response,
            exception=exception,
        )

        return is_angel_rate_limit_failure(
            classification
        )

    @staticmethod
    def _normalized_response_status(response):
        """Return True, False, or None for an Angel response envelope."""

        if not isinstance(response, dict):
            return None

        if "status" in response:
            raw_status = response.get("status")
        elif "success" in response:
            raw_status = response.get("success")
        else:
            return None

        if raw_status is True:
            return True

        if raw_status is False:
            return False

        if isinstance(raw_status, str):
            normalized = raw_status.strip().lower()

            if normalized in {
                "true",
                "success",
                "successful",
            }:
                return True

            if normalized in {
                "false",
                "failure",
                "failed",
                "error",
            }:
                return False

        return None

    @staticmethod
    def _response_error_code(response):
        """Return a normalized Angel error code without guessing."""

        if not isinstance(response, dict):
            return ""

        value = response.get(
            "errorcode",
            response.get(
                "errorCode",
                "",
            ),
        )

        if value is None:
            return ""

        return str(value).strip().upper()

    @staticmethod
    def _response_message(response):
        """Return a bounded sanitized Angel response message."""

        if not isinstance(response, dict):
            return ""

        return _safe_provider_reason(
            response.get(
                "message",
                "",
            )
        )

    @classmethod
    def _is_authentication_error(
        cls,
        response=None,
        exception=None,
    ):
        """Classify documented Angel authentication/session failures."""

        from services.broker.angel_provider_failure import (
            classify_angel_provider_failure,
            is_angel_authentication_failure,
        )

        classification = classify_angel_provider_failure(
            response=response,
            exception=exception,
        )

        return is_angel_authentication_failure(
            classification
        )

    @staticmethod
    def _is_retryable_exception(
        exception,
    ):
        """
        Detect temporary network or service failures.

        Because SmartAPI may wrap requests/urllib3
        exceptions, classification uses the exception
        class name and message.
        """

        exception_name = (
            exception.__class__.__name__
            .lower()
        )

        message = str(
            exception
        ).lower()

        retryable_names = (
            "timeout",
            "connecttimeout",
            "readtimeout",
            "connectionerror",
            "maxretryerror",
        )

        retryable_messages = (
            "timed out",
            "timeout",
            "connection reset",
            "connection aborted",
            "connection refused",
            "temporarily unavailable",
            "temporary failure",
            "max retries exceeded",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
            "too many requests",
        )

        return (
            any(
                term in exception_name
                for term
                in retryable_names
            )
            or any(
                term in message
                for term
                in retryable_messages
            )
        )

    @staticmethod
    def _is_retryable_response(
        response,
    ):
        """
        Detect API responses representing
        temporary service failures.
        """

        if not isinstance(
            response,
            dict,
        ):
            return False

        message = str(
            response.get(
                "message",
                "",
            )
        ).lower()

        error_code = str(
            response.get(
                "errorcode",
                "",
            )
        ).lower()

        combined = (
            f"{message} {error_code}"
        )

        retryable_terms = (
            "timeout",
            "temporarily unavailable",
            "temporary failure",
            "service unavailable",
            "server error",
            "internal server error",
            "bad gateway",
            "gateway timeout",
            "too many requests",
            "rate limit",
        )

        return any(
            term in combined
            for term
            in retryable_terms
        )

    # ---------------------------------
    # RESPONSE VALIDATION
    # ---------------------------------

    @classmethod
    def _validate_response(
        cls,
        response,
        request_name,
        *,
        require_data=True,
    ):
        """Validate the common Angel response envelope."""

        if response is None or response == {} or response == []:
            raise RuntimeError(
                f"Angel One returned an empty "
                f"{request_name} response."
            )

        if not isinstance(response, dict):
            raise RuntimeError(
                f"Angel One returned an invalid "
                f"{request_name} response type."
            )

        status = cls._normalized_response_status(
            response
        )

        if status is None:
            raise RuntimeError(
                f"Angel One returned an invalid "
                f"{request_name} response envelope."
            )

        if status is False:
            error_code = cls._response_error_code(
                response
            )
            message = cls._response_message(
                response
            )

            details = []

            if error_code:
                details.append(error_code)

            if message:
                details.append(message)

            reason = (
                " - ".join(details)
                if details
                else "Unknown error"
            )

            raise RuntimeError(
                f"Angel One {request_name} "
                f"request failed: {reason}"
            )

        if "data" not in response and require_data:
            raise RuntimeError(
                f"Angel One returned a successful "
                f"{request_name} response without data."
            )

        if require_data:
            data = response["data"]
            if data is None or (
                isinstance(data, str)
                and data.strip().lower() == "null"
            ):
                raise RuntimeError(
                    f"Angel One returned a successful "
                    f"{request_name} response without usable data."
                )

        return response

    @classmethod
    def _provider_failure_error(
        cls,
        *,
        request_name,
        attempts,
        response=None,
        exception=None,
        detail="Provider request failed.",
    ):
        """Build a typed, sanitized provider failure without retaining payloads."""
        from services.broker.angel_provider_failure import (
            classify_angel_provider_failure,
        )

        return BrokerMarketDataRequestError(
            request_name,
            attempts,
            "provider_failure",
            _safe_provider_reason(detail),
            provider_failure_kind=(
                classify_angel_provider_failure(
                    response=response,
                    exception=exception,
                )
            ),
        )

    # ---------------------------------
    # RESILIENT REQUEST EXECUTION
    # ---------------------------------

    def _execute_request(
        self,
        request_callable,
        request_name,
        cache_key=None,
        require_data=True,
    ):
        debug_print(f"REQUEST -> instance={id(self)} request={request_name}")
        """
        Execute a read-only SmartAPI request
        with retry and authentication recovery.

        Retry behavior:
        - Temporary network errors are retried.
        - Temporary API failures are retried.
        - Authentication failures trigger one
          fresh login before retrying.
        - Permanent failures stop immediately.
        """

        if cache_key is not None:
            cached = self.request_controller.get_cached(
                cache_key,
                request_name,
            )
            if cached is not None:
                return cached

        delay = (
            self.retry_delay_seconds
        )

        last_exception = None

        authentication_retry_used = False

        rate_limit_attempts = 0

        # A configured rate-limit retry budget must not be silently reduced by
        # the older general retry budget.
        maximum_attempts = max(
            self.max_retries,
            self.max_rate_limit_retries + 1,
        )

        for attempt in range(
            1,
            maximum_attempts + 1,
        ):

            try:
                self._ensure_authenticated()

                self.request_controller.wait_for_slot(
                    request_name,
                    attempt,
                )

                # Pacing can span midnight.  Recheck at the actual outbound
                # boundary so a session authenticated on the prior local day
                # is never used for the SDK request.
                self._ensure_authenticated()

                try:
                    response = request_callable()
                    LOGGER.info("broker_request request_type=%s endpoint_category=%s response_type=%s", request_name, request_name, type(response).__name__)
                finally:
                    self.request_controller.mark_request_complete(
                        request_name
                    )
                if (
                    self._is_rate_limit_error(
                        response=response,
                    )
                ):
                    rate_limit_attempts += 1

                    if (
                        rate_limit_attempts
                        > self.max_rate_limit_retries
                    ):
                        raise BrokerMarketDataRequestError(
                            request_name,
                            rate_limit_attempts,
                            "rate_limited",
                            _safe_provider_reason(response.get("message", "Unknown rate-limit error")),
                        )

                    self.request_controller.record_rate_limit(
                        request_name,
                        rate_limit_attempts,
                        self.retry_backoff_multiplier,
                    )

                    continue

                # -------------------------
                # SESSION EXPIRED
                # -------------------------

                if self._is_authentication_error(
                    response=response,
                ):

                    if authentication_retry_used:
                        raise self._provider_failure_error(
                            request_name=request_name,
                            attempts=attempt,
                            response=response,
                            detail=(
                                "Provider request failed after session "
                                "re-authentication."
                            ),
                        )

                    authentication_retry_used = True

                    self._reset_session()

                    self.login(
                        force=True
                    )

                    continue

                # -------------------------
                # TEMPORARY API FAILURE
                # -------------------------

                if self._is_retryable_response(
                    response
                ):

                    if (
                        attempt
                        >= self.max_retries
                    ):
                        raise self._provider_failure_error(
                            request_name=request_name,
                            attempts=attempt,
                            response=response,
                            detail="Provider request retry budget exhausted.",
                        )

                    time.sleep(
                        delay
                    )

                    delay *= (
                        self.retry_backoff_multiplier
                    )

                    continue

                # -------------------------
                # NORMAL RESPONSE
                # -------------------------

                if (
                    self._normalized_response_status(response)
                    is False
                ):
                    raise self._provider_failure_error(
                        request_name=request_name,
                        attempts=attempt,
                        response=response,
                        detail="Provider returned an unsuccessful response.",
                    )

                validated = self._validate_response(
                    response,
                    request_name,
                    require_data=require_data,
                )

                self.request_controller.record_success(
                        request_name,
                    )

                if cache_key is not None:
                        self.request_controller.cache(
                            cache_key,
                            validated,
                        )

                return validated

            except Exception as exc:
                LOGGER.warning("broker_request_failed request_type=%s error_type=%s retry=%s reason=%s", request_name, type(exc).__name__, attempt, _safe_provider_reason(exc))
                last_exception = exc

                if isinstance(
                    exc,
                    BrokerMarketDataRequestError,
                ):
                    raise

                if self._is_rate_limit_error(exception=exc):
                    rate_limit_attempts += 1
                    if rate_limit_attempts > self.max_rate_limit_retries:
                        raise BrokerMarketDataRequestError(
                            request_name,
                            rate_limit_attempts,
                            "rate_limited",
                            _safe_provider_reason(exc),
                        ) from exc
                    self.request_controller.record_rate_limit(
                        request_name,
                        rate_limit_attempts,
                        self.retry_backoff_multiplier,
                    )
                    continue

                # -------------------------
                # AUTHENTICATION EXCEPTION
                # -------------------------

                if self._is_authentication_error(
                    exception=exc,
                ):

                    if authentication_retry_used:
                        raise self._provider_failure_error(
                            request_name=request_name,
                            attempts=attempt,
                            exception=exc,
                            detail=(
                                "Provider request failed after session "
                                "re-authentication."
                            ),
                        ) from exc

                    if not authentication_retry_used:

                        authentication_retry_used = True

                        self._reset_session()

                        try:
                            self.login(
                                force=True
                            )

                        except Exception as login_exc:
                            raise self._provider_failure_error(
                                request_name=request_name,
                                attempts=attempt,
                                exception=login_exc,
                                detail=(
                                    "Provider session re-authentication "
                                    "failed."
                                ),
                            ) from login_exc

                        continue

                # -------------------------
                # NON-RETRYABLE FAILURE
                # -------------------------

                if not self._is_retryable_exception(
                    exc
                ):
                    raise

                # -------------------------
                # RETRIES EXHAUSTED
                # -------------------------

                if (
                    attempt
                    >= self.max_retries
                ):
                    break

                # -------------------------
                # WAIT BEFORE RETRY
                # -------------------------

                time.sleep(
                    delay
                )

                delay *= (
                    self.retry_backoff_multiplier
                )

        raise self._provider_failure_error(
            request_name=request_name,
            attempts=maximum_attempts,
            exception=last_exception,
            detail=(
                f"Provider request failed after {self.max_retries} "
                "attempts."
            ),
        ) from last_exception

    @staticmethod
    def _market_data_cache_key(mode, exchange_tokens):
        return (
            "market-data",
            mode,
            tuple(sorted(
                (str(exchange).upper(), tuple(sorted(map(str, tokens))))
                for exchange, tokens in exchange_tokens.items()
            )),
        )

    @staticmethod
    def _validate_market_data_payload(
        response,
    ):
        """Validate Angel batched quote payload shape."""

        data = response.get("data")

        if not isinstance(data, dict):
            raise RuntimeError(
                "Angel One market-data response "
                "contains invalid data."
            )

        fetched = data.get("fetched")
        unfetched = data.get("unfetched")

        if not isinstance(fetched, list):
            raise RuntimeError(
                "Angel One market-data response "
                "contains invalid fetched data."
            )

        if not isinstance(unfetched, list):
            raise RuntimeError(
                "Angel One market-data response "
                "contains invalid unfetched data."
            )

        for item in fetched:
            if not isinstance(item, dict):
                raise RuntimeError(
                    "Angel One market-data response "
                    "contains an invalid fetched item."
                )

        for item in unfetched:
            if not isinstance(item, dict):
                raise RuntimeError(
                    "Angel One market-data response "
                    "contains an invalid unfetched item."
                )

        return response

    @staticmethod
    def _validate_historical_payload(
        response,
    ):
        """Validate Angel historical candle payload shape."""

        data = response.get("data")

        if not isinstance(data, list):
            raise BrokerMarketDataRequestError(
                "historical-data",
                1,
                "invalid_response",
                "Historical payload data is not a list.",
            )

        if not data:
            raise BrokerMarketDataRequestError(
                "historical-data",
                1,
                "empty_data",
                "Historical payload data is empty.",
            )

        try:
            from services.data_normalizer import (
                normalize_angel_candles,
            )

            normalize_angel_candles(
                data
            )
        except (TypeError, ValueError) as exc:
            raise BrokerMarketDataRequestError(
                "historical-data",
                1,
                "normalization_failed",
                "Historical payload contains invalid candle rows.",
            ) from exc

        return response

    @staticmethod
    def _validate_option_greeks_payload(
        response,
    ):
        """Validate Angel option-Greeks payload shape."""

        data = response.get("data")

        if not isinstance(data, list):
            raise RuntimeError(
                "Angel One Option Greeks response "
                "contains invalid data."
            )

        for item in data:
            if not isinstance(item, dict):
                raise RuntimeError(
                    "Angel One Option Greeks response "
                    "contains an invalid item."
                )

        return response

    @staticmethod
    def _normalized_market_identity(
        exchange,
        symboltoken,
    ):
        normalized_exchange = str(
            exchange
        ).strip().upper()

        normalized_token = str(
            symboltoken
        ).strip()

        if not normalized_exchange:
            raise ValueError(
                "exchange is required."
            )

        if not normalized_token:
            raise ValueError(
                "symboltoken is required."
            )

        return (
            normalized_exchange,
            normalized_token,
        )

    # ---------------------------------
    # LIVE MARKET DATA
    # ---------------------------------

    def get_market_data(
        self,
        mode,
        exchange_tokens,
    ):
        """
        Fetch live market data.

        Parameters
        ----------
        mode : str
            LTP, OHLC, or FULL.

        exchange_tokens : dict
            Example:
            {
                "NSE": ["99926000"]
            }
        """

        valid_modes = {
            "LTP",
            "OHLC",
            "FULL",
        }

        mode = str(
            mode
        ).upper()

        if mode not in valid_modes:
            raise ValueError(
                "mode must be one of: "
                "LTP, OHLC, FULL"
            )

        if not isinstance(
            exchange_tokens,
            dict,
        ):
            raise ValueError(
                "exchange_tokens must "
                "be a dictionary."
            )

        if not exchange_tokens:
            raise ValueError(
                "exchange_tokens cannot be empty."
            )

        response = self._execute_request(
            request_callable=lambda: (
                self.api.getMarketData(
                    mode,
                    exchange_tokens,
                )
            ),
            request_name="market-data",
            cache_key=self._market_data_cache_key(
                mode,
                exchange_tokens,
            ),
        )

        return self._validate_market_data_payload(
            response
        )
    def get_ltp(
        self,
        exchange,
        tradingsymbol,
        symboltoken,
    ):
        expected_exchange, expected_token = (
            self._normalized_market_identity(
                exchange,
                symboltoken,
            )
        )

        response = self.get_market_data(
            "LTP",
            {
                expected_exchange: [
                    expected_token
                ],
            },
        )

        payload = response["data"]
        fetched = payload["fetched"]
        unfetched = payload["unfetched"]

        matching_unfetched = [
            item
            for item in unfetched
            if (
                str(
                    item.get(
                        "exchange",
                        "",
                    )
                ).strip().upper()
                == expected_exchange
                and str(
                    item.get(
                        "symbolToken",
                        item.get(
                            "symboltoken",
                            "",
                        ),
                    )
                ).strip()
                == expected_token
            )
        ]

        if matching_unfetched:
            item = matching_unfetched[0]

            error_code = str(
                item.get(
                    "errorCode",
                    item.get(
                        "errorcode",
                        "",
                    ),
                )
            ).strip()

            reason = _safe_provider_reason(
                item.get(
                    "message",
                    "Unable to fetch requested token",
                )
            )

            detail = (
                f"{error_code} - {reason}"
                if error_code
                else reason
            )

            raise RuntimeError(
                "Angel One failed to fetch "
                f"{expected_exchange}:"
                f"{expected_token}: {detail}"
            )

        matches = []

        for item in fetched:
            item_exchange = str(
                item.get(
                    "exchange",
                    "",
                )
            ).strip().upper()

            item_token = str(
                item.get(
                    "symbolToken",
                    item.get(
                        "symboltoken",
                        "",
                    ),
                )
            ).strip()

            if (
                item_exchange
                == expected_exchange
                and item_token
                == expected_token
            ):
                matches.append(item)

        if len(matches) != 1:
            raise RuntimeError(
                "Angel One market-data response "
                "did not contain exactly one matching "
                f"{expected_exchange}:{expected_token} quote."
            )

        data = matches[0]

        try:
            ltp = float(data["ltp"])
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Angel One market-data response "
                "contains an invalid LTP."
            ) from exc

        if ltp <= 0:
            raise RuntimeError(
                "Angel One market-data response "
                "contains a non-positive LTP."
            )

        returned_symbol = str(
            data.get(
                "tradingSymbol",
                data.get(
                    "tradingsymbol",
                    tradingsymbol,
                ),
            )
        ).strip()

        return {
            "status": True,
            "data": {
                "ltp": ltp,
                "tradingsymbol": (
                    returned_symbol
                    or str(tradingsymbol)
                ),
                "symboltoken": expected_token,
                "exchange": expected_exchange,
            },
        }

    # ---------------------------------
    # HISTORICAL CANDLE DATA
    # ---------------------------------

    def get_historical_data(
        self,
        exchange,
        symboltoken,
        interval,
        fromdate,
        todate,
    ):
        """
        Fetch historical candle data.
        """

        if not exchange:
            raise ValueError(
                "exchange is required."
            )

        if not symboltoken:
            raise ValueError(
                "symboltoken is required."
            )

        if not interval:
            raise ValueError(
                "interval is required."
            )

        if not fromdate:
            raise ValueError(
                "fromdate is required."
            )

        if not todate:
            raise ValueError(
                "todate is required."
            )

        params = {
            "exchange": exchange,
            "symboltoken": symboltoken,
            "interval": interval,
            "fromdate": fromdate,
            "todate": todate,
        }


        response = self._execute_request(
            request_callable=lambda: (
                self.api.getCandleData(
                    params
                )
            ),
            request_name="historical-data",
            cache_key=None,
            require_data=False,
        )

        return self._validate_historical_payload(
            response
        )

    # ---------------------------------
    # OPTION GREEKS
    # ---------------------------------

    def get_option_greeks(
        self,
        name,
        expiry_date,
    ):
        """
        Fetch option Greeks from Angel One.

        Returns data such as:
        - Delta
        - Gamma
        - Theta
        - Vega
        - Implied volatility

        Read-only.
        """

        if not name:
            raise ValueError(
                "Option underlying name "
                "is required."
            )

        if not expiry_date:
            raise ValueError(
                "Option expiry date "
                "is required."
            )

        params = {
            "name": str(
                name
            ).upper(),
            "expirydate": expiry_date,
        }

        response = self._execute_request(
            request_callable=lambda: (
                self.api.optionGreek(
                    params
                )
            ),
            request_name="Option Greeks",
            cache_key=(
                "option-greeks",
                params["name"],
                expiry_date,
            ),
        )

        return self._validate_option_greeks_payload(
            response
        )
    # ---------------------------------
    # OPTION CHAIN (LIVE)
    # ---------------------------------

    def get_option_chain(
        self,
        exchange_tokens,
    ):
        """
        Fetch live option chain quotes.

        Parameters
        ----------
        exchange_tokens : dict

        Example
        -------
        {
            "NFO": [
                "12345",
                "12346",
                ...
            ]
        }

        Returns
        -------
        SmartAPI FULL market data response.
        """

        if not exchange_tokens:
            raise ValueError(
                "exchange_tokens cannot be empty."
            )

        return self.get_market_data(
            "FULL",
            exchange_tokens,
        )
