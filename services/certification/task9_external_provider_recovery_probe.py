"""Explicit one-request Task 9 historical recovery probe; no cycle execution."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from services.broker.market_data_control import (
    BrokerMarketDataRequestError,
)
from services.broker.angel_provider_failure import (
    classify_angel_provider_failure,
)
from services.broker.shared_client import (
    get_certification_market_client,
)
from services.certification.task9_external_provider_blocker import (
    Task9ExternalProviderBlockerError,
    Task9ExternalProviderBlockerStore,
)
from services.data_normalizer import (
    normalize_angel_candles,
)
from services.historical_provider_cooldown import (
    HistoricalProviderCooldown,
)
from services.historical_request_gate import (
    HistoricalRequestGate,
)
from services.market.live_multi_timeframe_data import (
    required_closed_candle_at,
)


IST = ZoneInfo("Asia/Kolkata")

PROBE_EXCHANGE = "NSE"
PROBE_SYMBOLTOKEN = "99926000"
PROBE_INTERVAL = "FIVE_MINUTE"
PROBE_TIMEFRAME = "5m"

RATE_LIMIT_FAILURE_TYPE = "rate_limited"
RATE_LIMIT_REASON = "HISTORICAL-DATA_RATE_LIMITED"
GENERIC_FAILURE_REASON = "HISTORICAL-DATA_UNAVAILABLE"

_PROVIDER_FAILURE_REASONS = {
    "RATE_LIMIT": RATE_LIMIT_REASON,
    "AUTH_INVALID": "HISTORICAL-DATA_AUTH_INVALID",
    "AUTH_EXPIRED": "HISTORICAL-DATA_AUTH_EXPIRED",
    "SESSION_EXPIRED": "HISTORICAL-DATA_SESSION_EXPIRED",
    "SYMBOL_INVALID": "HISTORICAL-DATA_SYMBOL_INVALID",
    "SYMBOL_LOOKUP_FAILED": "HISTORICAL-DATA_SYMBOL_LOOKUP_FAILED",
    "PROVIDER_TRANSIENT": "HISTORICAL-DATA_PROVIDER_TRANSIENT",
    "PROVIDER_INTERNAL": "HISTORICAL-DATA_PROVIDER_INTERNAL",
    "UNKNOWN_PROVIDER_ERROR": "HISTORICAL-DATA_UNKNOWN_PROVIDER_ERROR",
}

_PROBE_VALIDATION_FAILURE_REASONS = {
    "RECOVERY_PROBE_INVALID_RESPONSE": "HISTORICAL-DATA_INVALID_RESPONSE",
    "RECOVERY_PROBE_PROVIDER_UNSUCCESSFUL": "HISTORICAL-DATA_PROVIDER_UNSUCCESSFUL",
    "RECOVERY_PROBE_EMPTY_DATA": "HISTORICAL-DATA_EMPTY_DATA",
    "RECOVERY_PROBE_NORMALIZATION_FAILED": "HISTORICAL-DATA_NORMALIZATION_FAILED",
    "RECOVERY_PROBE_EMPTY_NORMALIZED_DATA": "HISTORICAL-DATA_EMPTY_NORMALIZED_DATA",
    "RECOVERY_PROBE_INVALID_NORMALIZED_DATA": "HISTORICAL-DATA_INVALID_NORMALIZED_DATA",
}

_HISTORICAL_TYPED_FAILURE_REASONS = {
    "invalid_response": "HISTORICAL-DATA_INVALID_RESPONSE",
    "empty_data": "HISTORICAL-DATA_EMPTY_DATA",
    "normalization_failed": "HISTORICAL-DATA_NORMALIZATION_FAILED",
}


def _require_aware_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(field_name)

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(field_name)

    return value


def bootstrap_verified_blocker(
    *,
    persistence_root,
    official_run_id,
    observed_at,
):
    """
    Persist the already-verified Task 9.23 external quota blocker.

    This path never performs a provider request.
    Existing ACTIVE or CLEARED blocker state is preserved unchanged.
    """

    observed_at = _require_aware_datetime(
        observed_at,
        field_name="observed_at",
    )

    store = Task9ExternalProviderBlockerStore(
        persistence_root
    )

    existing = store.load(
        official_run_id
    )

    if existing is not None:
        return existing

    return store.record(
        official_run_id,
        observed_at=observed_at,
        probe_at=observed_at,
        probe_result="RATE_LIMITED",
        failure_reason=RATE_LIMIT_REASON,
    )


def record_verified_runtime_rate_limit(
    *,
    persistence_root,
    official_run_id,
    observed_at,
    incident_id,
):
    """Record already-retained runtime evidence without a provider operation."""

    observed_at = _require_aware_datetime(
        observed_at,
        field_name="observed_at",
    )
    return Task9ExternalProviderBlockerStore(
        persistence_root
    ).record_runtime_rate_limit(
        official_run_id,
        observed_at=observed_at,
        incident_id=incident_id,
    )


def _is_rate_limited_broker_error(
    exc: BrokerMarketDataRequestError,
) -> bool:
    """
    Classify only from the structured broker failure contract.

    Do not classify arbitrary exception text as a rate limit.
    """

    failure = getattr(
        exc,
        "failure",
        None,
    )

    return (
        isinstance(failure, dict)
        and failure.get("failure_type")
        == RATE_LIMIT_FAILURE_TYPE
    )


def _validate_probe_response(response):
    """
    Validate recovery response before the external blocker may be cleared.
    """

    if not isinstance(response, dict):
        raise ValueError(
            "RECOVERY_PROBE_INVALID_RESPONSE"
        )

    if response.get("status") is not True:
        raise ValueError(
            "RECOVERY_PROBE_PROVIDER_UNSUCCESSFUL"
        )

    data = response.get("data")

    if not isinstance(data, list) or not data:
        raise ValueError(
            "RECOVERY_PROBE_EMPTY_DATA"
        )

    try:
        normalized = normalize_angel_candles(
            data
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "RECOVERY_PROBE_NORMALIZATION_FAILED"
        ) from exc

    if normalized is None:
        raise ValueError(
            "RECOVERY_PROBE_NORMALIZATION_FAILED"
        )

    try:
        if len(normalized) < 1:
            raise ValueError(
                "RECOVERY_PROBE_EMPTY_NORMALIZED_DATA"
            )
    except TypeError as exc:
        raise ValueError(
            "RECOVERY_PROBE_INVALID_NORMALIZED_DATA"
        ) from exc

    return normalized


def _sanitized_probe_failure(
    exc: BaseException,
) -> tuple[str, str, bool]:
    """Return only stable failure metadata safe for blocker persistence."""
    if isinstance(exc, BrokerMarketDataRequestError):
        failure = getattr(exc, "failure", None)
        if isinstance(failure, dict):
            typed_reason = _HISTORICAL_TYPED_FAILURE_REASONS.get(
                failure.get("failure_type")
            )
            if typed_reason is not None:
                return "FAILED", typed_reason, False

            provider_failure_kind = failure.get(
                "provider_failure_kind"
            )
            if isinstance(provider_failure_kind, str):
                normalized = provider_failure_kind.strip().upper()
                if normalized == "RATE_LIMIT":
                    return "RATE_LIMITED", RATE_LIMIT_REASON, True
                reason = _PROVIDER_FAILURE_REASONS.get(normalized)
                if reason is not None:
                    return "FAILED", reason, False

    if isinstance(exc, ValueError):
        code = str(exc)
        reason = _PROBE_VALIDATION_FAILURE_REASONS.get(code)
        if reason is not None:
            return "FAILED", reason, False

    classification = classify_angel_provider_failure(
        exception=exc,
    )

    if isinstance(classification, str):
        normalized = classification.strip().upper()
        if normalized == "RATE_LIMIT":
            return "RATE_LIMITED", RATE_LIMIT_REASON, True

        reason = _PROVIDER_FAILURE_REASONS.get(normalized)
        if (
            normalized == "UNKNOWN_PROVIDER_ERROR"
            and not _has_structured_provider_evidence(exc)
        ):
            reason = None
        if reason is not None:
            return "FAILED", reason, False

    return "FAILED", GENERIC_FAILURE_REASON, False


def _has_structured_provider_evidence(
    exc: BaseException,
) -> bool:
    """Distinguish an unknown provider failure from a bare local exception."""
    current: BaseException | None = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if any(
            getattr(current, attribute, None) is not None
            for attribute in (
                "errorcode",
                "errorCode",
                "status_code",
                "statusCode",
                "response",
            )
        ):
            return True
        current = (
            current.__cause__
            if current.__cause__ is not None
            else current.__context__
        )

    return False


def _record_sanitized_probe_failure(
    store,
    *,
    official_run_id,
    observed_at,
    exc: BaseException,
):
    probe_result, failure_reason, increment_occurrence = (
        _sanitized_probe_failure(exc)
    )
    return store.record(
        official_run_id,
        observed_at=observed_at,
        probe_at=observed_at,
        probe_result=probe_result,
        failure_reason=failure_reason,
        increment_occurrence=increment_occurrence,
    )


def run_recovery_probe(
    *,
    persistence_root,
    official_run_id,
    now,
    client=None,
    gate=None,
    cooldown=None,
):
    """
    Perform at most one historical provider request.

    This path never executes a Task 9 certification cycle and never counts.
    """

    now = _require_aware_datetime(
        now,
        field_name="now",
    )

    store = Task9ExternalProviderBlockerStore(
        persistence_root
    )

    blocker = store.load(
        official_run_id
    )

    if (
        blocker is None
        or blocker["status"] != "ACTIVE"
    ):
        raise Task9ExternalProviderBlockerError(
            "RECOVERY_PROBE_NOT_REQUIRED"
        )

    next_probe_not_before = datetime.fromisoformat(
        blocker["next_probe_not_before"]
    )

    if now < next_probe_not_before:
        raise Task9ExternalProviderBlockerError(
            "RECOVERY_PROBE_NOT_YET_ALLOWED"
        )

    store.acquire_probe_lease()

    try:
        cooldown_authority = (
            cooldown
            if cooldown is not None
            else HistoricalProviderCooldown(
                Path(
                    "data/market_data_cache/"
                    "angel_historical_provider_cooldown.json"
                )
            )
        )

        if cooldown_authority.active() is not None:
            raise Task9ExternalProviderBlockerError(
                "RECOVERY_PROBE_HISTORICAL_COOLDOWN_ACTIVE"
            )

        local_now = now.astimezone(
            IST
        ).replace(
            second=0,
            microsecond=0,
        )

        required = required_closed_candle_at(
            PROBE_TIMEFRAME,
            local_now,
            exchange=PROBE_EXCHANGE,
        )

        if required is None:
            raise Task9ExternalProviderBlockerError(
                "RECOVERY_PROBE_NO_COMPLETED_CANDLE"
            )

        start = required
        end = required + timedelta(
            minutes=5
        )

        gate_authority = (
            gate
            if gate is not None
            else HistoricalRequestGate(
                Path(
                    "data/market_data_cache/"
                    "angel_historical_request_gate.json"
                )
            )
        )

        gate_authority.acquire()

        market_client = (
            client
            if client is not None
            else get_certification_market_client()
        )

        try:
            response = market_client.get_historical_data(
                exchange=PROBE_EXCHANGE,
                symboltoken=PROBE_SYMBOLTOKEN,
                interval=PROBE_INTERVAL,
                fromdate=start.strftime(
                    "%Y-%m-%d %H:%M"
                ),
                todate=end.strftime(
                    "%Y-%m-%d %H:%M"
                ),
            )

            _validate_probe_response(
                response
            )

        except BrokerMarketDataRequestError as exc:
            if _is_rate_limited_broker_error(
                exc
            ):
                return store.record(
                    official_run_id,
                    observed_at=now,
                    probe_at=now,
                    probe_result="RATE_LIMITED",
                    failure_reason=RATE_LIMIT_REASON,
                )

            return _record_sanitized_probe_failure(
                store,
                official_run_id=official_run_id,
                observed_at=now,
                exc=exc,
            )

        except Exception as exc:
            return _record_sanitized_probe_failure(
                store,
                official_run_id=official_run_id,
                observed_at=now,
                exc=exc,
            )

        return store.clear(
            official_run_id,
            observed_at=now,
        )

    finally:
        store.release_probe_lease()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Task 9 explicit historical provider "
            "recovery probe"
        )
    )

    parser.add_argument(
        "--persistence-root",
        required=True,
    )

    parser.add_argument(
        "--official-run-id",
        required=True,
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--bootstrap-verified-rate-limit-at")
    mode.add_argument("--record-verified-runtime-rate-limit-at")
    parser.add_argument("--incident-id")

    args = parser.parse_args(
        argv
    )

    if args.incident_id and not args.record_verified_runtime_rate_limit_at:
        parser.error(
            "--incident-id requires --record-verified-runtime-rate-limit-at"
        )

    if args.bootstrap_verified_rate_limit_at:
        observed_at = datetime.fromisoformat(
            args.bootstrap_verified_rate_limit_at
        )

        result = bootstrap_verified_blocker(
            persistence_root=args.persistence_root,
            official_run_id=args.official_run_id,
            observed_at=observed_at,
        )

        print(
            "TASK9_EXTERNAL_PROVIDER_BLOCKER_ACTIVE "
            f"blocker_code={result['blocker_code']} "
            f"next_probe_not_before="
            f"{result['next_probe_not_before']}"
        )

    elif args.record_verified_runtime_rate_limit_at:
        if not args.incident_id:
            parser.error(
                "--record-verified-runtime-rate-limit-at requires --incident-id"
            )
        observed_at = datetime.fromisoformat(
            args.record_verified_runtime_rate_limit_at
        )
        result = record_verified_runtime_rate_limit(
            persistence_root=args.persistence_root,
            official_run_id=args.official_run_id,
            observed_at=observed_at,
            incident_id=args.incident_id,
        )
        print(
            "TASK9_EXTERNAL_PROVIDER_RUNTIME_RATE_LIMIT_RECORDED "
            f"blocker_code={result['blocker_code']} "
            f"next_probe_not_before={result['next_probe_not_before']}"
        )
    else:
        result = run_recovery_probe(
            persistence_root=args.persistence_root,
            official_run_id=args.official_run_id,
            now=datetime.now(IST),
        )

        print(
            f"RECOVERY_PROBE_"
            f"{result['last_probe_result']} "
            f"blocker_code="
            f"{result['blocker_code']} "
            f"status={result['status']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
