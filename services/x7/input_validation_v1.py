"""Pure five-market X7 external-context readiness; no external I/O or scoring."""

from __future__ import annotations

import math
from datetime import datetime

from services.x7.contracts_v1 import (
    INDEX_MARKETS,
    X7ContextCaptureV1,
    X7ContextValidationV1,
)


def _fresh(row: object, *, as_of: datetime, max_age_seconds: float) -> bool:
    return (
        getattr(row, "status") == "AVAILABLE"
        and getattr(row, "available_at") is not None
        and getattr(row, "available_at") <= as_of
        and getattr(row, "observed_at") <= as_of
        and 0 <= (as_of - getattr(row, "observed_at")).total_seconds() <= max_age_seconds
    )


def validate_x7_context_v1(
    capture: X7ContextCaptureV1,
    *,
    global_max_age_seconds: float,
    institutional_max_age_seconds: float,
    event_max_age_seconds: float,
) -> X7ContextValidationV1:
    """Assess supplied captured facts, never create or fetch missing facts.

    Absence of a family is explicit UNAVAILABLE; index-only India cash-flow
    data never becomes an MCX commodity positioning claim. EVENT availability
    means a confirmed, known scheduled fact, not a trade-entry decision.
    """
    if not isinstance(capture, X7ContextCaptureV1):
        raise TypeError("An immutable X7 context capture is required")
    for name, budget in (
        ("global", global_max_age_seconds),
        ("institutional", institutional_max_age_seconds),
        ("event", event_max_age_seconds),
    ):
        if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
            raise ValueError(f"{name} freshness budget must be positive and finite")
    blockers: list[str] = []
    warnings: list[str] = []
    if not capture.capture_verified:
        blockers.append("CAPTURE_UNVERIFIED")
    if capture.historical_retrieval or not capture.point_in_time_verified:
        warnings.append("POINT_IN_TIME_AVAILABILITY_UNPROVEN")

    global_ok = any(
        row.value_verified
        and row.source_verified
        and _fresh(row, as_of=capture.as_of, max_age_seconds=global_max_age_seconds)
        for row in capture.global_observations
    )
    if not global_ok:
        warnings.append("GLOBAL_CONTEXT_UNAVAILABLE")
    if len(capture.global_observations) > 1 and not all(
        row.value_verified
        and row.source_verified
        and _fresh(row, as_of=capture.as_of, max_age_seconds=global_max_age_seconds)
        for row in capture.global_observations
    ):
        warnings.append("GLOBAL_CONTEXT_PARTIALLY_VERIFIED")

    institutional_ok = capture.market in INDEX_MARKETS and any(
        row.values_verified
        and row.publication_state == "FINAL"
        and _fresh(row, as_of=capture.as_of, max_age_seconds=institutional_max_age_seconds)
        for row in capture.institutional_flows
    )
    if not institutional_ok:
        warnings.append("INSTITUTIONAL_CONTEXT_UNAVAILABLE")

    event_ok = any(
        row.confirmed
        and row.source_verified
        and _fresh(row, as_of=capture.as_of, max_age_seconds=event_max_age_seconds)
        for row in capture.scheduled_events
    )
    if not event_ok:
        warnings.append("SCHEDULED_EVENT_CONTEXT_UNAVAILABLE")
    # An index cash-flow snapshot is intentionally not required for commodities.
    available = sum((global_ok, institutional_ok, event_ok))
    if blockers or available == 0:
        status = "UNAVAILABLE"
        if available == 0:
            blockers.append("NO_VERIFIED_CONTEXT_FAMILY")
    elif (
        available == 3
        and capture.point_in_time_verified
        and not capture.historical_retrieval
        and not warnings
    ):
        status = "AVAILABLE"
    else:
        status = "PARTIAL"
    return X7ContextValidationV1(
        market=capture.market,
        capture_id=capture.capture_id,
        as_of=capture.as_of,
        status=status,
        global_status="AVAILABLE" if global_ok else "UNAVAILABLE",
        institutional_status="AVAILABLE" if institutional_ok else "UNAVAILABLE",
        event_status="AVAILABLE" if event_ok else "UNAVAILABLE",
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        source_capture_sha256=capture.sha256(),
    )
