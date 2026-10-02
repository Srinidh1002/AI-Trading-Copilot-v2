"""Read-only, exact-type X5/X7 to X8 references. No data-provider calls.

A supplied detached digest and availability time are assertions by the caller,
not an independent guarantee of upstream source authenticity.
"""

from __future__ import annotations

from datetime import datetime

from services.x5.chain_validation_v1 import validate_x5_chain_v1
from services.x5.contracts_v1 import X5ChainCaptureV1, X5ChainValidationV1
from services.x7.contracts_v1 import _aware, _sha
from services.x7.research_view_v1 import X7ResearchViewV1
from services.x8.contracts_v1 import X8EvidenceReferenceV1, require_identity


def _time(value: datetime | None, *, as_of: datetime, observed_at: datetime) -> None:
    if value is not None and (not _aware(value) or value < observed_at or value > as_of):
        raise ValueError("Upstream result availability must be aware and within the capture")


def bind_x5_options_to_x8_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    source: X5ChainCaptureV1,
    validation: X5ChainValidationV1,
    expected_source_sha256: str,
    expected_validation_sha256: str,
    result_available_at: datetime | None,
    max_age_seconds: float,
) -> X8EvidenceReferenceV1:
    """Represent the supplied, independently hash-anchored X5 result once."""
    require_identity(market, session_id, capture_id, as_of)
    if type(source) is not X5ChainCaptureV1 or type(validation) is not X5ChainValidationV1:
        raise TypeError("Only original immutable X5 capture and validation are accepted")
    if not _sha(expected_source_sha256) or not _sha(expected_validation_sha256):
        raise ValueError("Detached X5 SHA-256 anchors are required")
    if (
        source.sha256() != expected_source_sha256
        or validation.sha256() != expected_validation_sha256
    ):
        raise ValueError("X5 source/validation differs from detached expected digests")
    if (
        validate_x5_chain_v1(source, max_age_seconds=max_age_seconds).sha256()
        != validation.sha256()
    ):
        raise ValueError("X5 validation is not reproducible from the original source")
    if (
        source.contract.market != market
        or source.session_id != session_id
        or source.capture_id != capture_id
        or source.as_of > as_of
        or validation.market != market
        or validation.capture_id != capture_id
        or validation.as_of != source.as_of
        or validation.source_capture_sha256 != expected_source_sha256
    ):
        raise ValueError("X5 market/session/capture/validation binding mismatch")
    _time(result_available_at, as_of=as_of, observed_at=source.as_of)
    pit = bool(
        source.point_in_time_verified
        and not source.historical_retrieval
        and source.capture_verified
        and source.timestamp_semantics_verified
        and result_available_at is not None
    )
    if validation.status == "UNAVAILABLE":
        state = "UNAVAILABLE"
    elif not pit:
        state = "UNVERIFIED"
    elif validation.status == "AVAILABLE":
        state = "AVAILABLE"
    else:
        state = "PARTIAL"
    return X8EvidenceReferenceV1(
        family="OPTIONS",
        source_id=f"X5:{source.source_id}",
        source_record_id=f"{session_id}:{capture_id}",
        source_sha256=expected_validation_sha256,
        observed_at=source.as_of,
        available_at=result_available_at,
        state=state,
        point_in_time_verified=pit,
    )


def bind_x7_context_to_x8_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    source: X7ResearchViewV1,
    expected_view_sha256: str,
    result_available_at: datetime | None,
) -> X8EvidenceReferenceV1:
    """Preserve MCX PARTIAL and retrospective X7 rather than upgrading either."""
    require_identity(market, session_id, capture_id, as_of)
    if type(source) is not X7ResearchViewV1 or not _sha(expected_view_sha256):
        raise TypeError("Exact immutable X7 research view and detached SHA-256 required")
    if source.sha256() != expected_view_sha256:
        raise ValueError("X7 research view differs from detached expected digest")
    capture = source.capture
    if (
        capture.market != market
        or capture.session_id != session_id
        or capture.capture_id != capture_id
        or capture.as_of > as_of
        or source.validation.source_capture_sha256 != capture.sha256()
    ):
        raise ValueError("X7 market/session/capture/provenance mismatch")
    _time(result_available_at, as_of=as_of, observed_at=capture.as_of)
    pit = bool(
        capture.capture_verified
        and capture.point_in_time_verified
        and not capture.historical_retrieval
        and result_available_at is not None
    )
    if source.status == "UNAVAILABLE":
        state = "UNAVAILABLE"
    elif not pit:
        state = "UNVERIFIED"
    elif source.status == "AVAILABLE":
        state = "AVAILABLE"
    else:
        state = "PARTIAL"
    return X8EvidenceReferenceV1(
        family="EXTERNAL_CONTEXT",
        source_id="X7_RESEARCH_VIEW_V1",
        source_record_id=f"{session_id}:{capture_id}",
        source_sha256=expected_view_sha256,
        observed_at=capture.as_of,
        available_at=result_available_at,
        state=state,
        point_in_time_verified=pit,
    )
