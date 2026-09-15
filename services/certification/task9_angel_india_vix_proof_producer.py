"""Task 9 India VIX proof production from certified retained capture.

This module performs no provider acquisition.

IndiaVixLiveReader remains the sole certified master-resolution and
FULL-quote owner. This adapter converts its immutable retained capture
into the Task 9 startup capability proof.
"""
from __future__ import annotations

from services.contracts.india_vix_capture_result_v1 import (
    IndiaVixCaptureResultV1,
)
from services.contracts.task9_angel_india_vix_proof_v1 import (
    Task9AngelIndiaVixProbeStatus,
    Task9AngelIndiaVixProofV1,
)


def _identity_verified(
    capture: IndiaVixCaptureResultV1,
) -> bool:
    return (
        capture.canonical_name == "INDIA_VIX"
        and capture.provider == "ANGEL_SMARTAPI"
        and capture.provider_symbol == "India VIX"
        and capture.provider_exchange == "NSE"
        and capture.instrument_type == "AMXIDX"
        and isinstance(
            capture.provider_token,
            str,
        )
        and bool(capture.provider_token.strip())
    )


def _reason(
    capture: IndiaVixCaptureResultV1,
) -> str:
    if capture.blockers:
        return capture.blockers[0]

    return (
        "INDIA_VIX_CAPTURE_"
        f"{capture.source_status}"
    )


def produce_task9_angel_india_vix_proof(
    capture: IndiaVixCaptureResultV1,
) -> Task9AngelIndiaVixProofV1:
    """Convert one retained certified VIX capture into Task 9 proof."""

    if type(capture) is not IndiaVixCaptureResultV1:
        raise TypeError("capture")

    identity_verified = _identity_verified(
        capture
    )

    if capture.source_status == "READY":
        status = (
            Task9AngelIndiaVixProbeStatus.AVAILABLE
        )
        reason = None
    elif capture.source_status in {
        "UNAVAILABLE",
        "STALE",
        "BLOCKED",
    }:
        status = (
            Task9AngelIndiaVixProbeStatus.UNAVAILABLE
        )
        reason = _reason(capture)
    else:
        # The source contract currently prevents this branch, but
        # retain fail-closed behavior if its enum evolves later.
        status = (
            Task9AngelIndiaVixProbeStatus.MALFORMED
        )
        reason = (
            "INDIA_VIX_CAPTURE_STATUS_INVALID"
        )

    return Task9AngelIndiaVixProofV1(
        proof_id=(
            "task9-angel-india-vix:"
            f"{capture.capture_id}:"
            f"{capture.evaluated_at.isoformat()}"
        ),
        observed_at=capture.evaluated_at,
        market="INDIA_VIX",
        exchange="NSE",
        instrument_type="AMXIDX",
        status=status,
        provider_timestamp=(
            capture.provider_timestamp
        ),
        ltp=(
            capture.current_value
        ),
        previous_close=(
            capture.previous_close
        ),
        identity_verified=identity_verified,
        source_ref=(
            "certified-india-vix-live-reader"
            if identity_verified
            else None
        ),
        incident_ref=None,
        sanitized_reason=reason,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "produce_task9_angel_india_vix_proof",
)
