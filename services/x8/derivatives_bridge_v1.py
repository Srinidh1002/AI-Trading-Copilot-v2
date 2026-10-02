"""X8-B3 detached X4 futures and X6 volatility research references.

X4's aggregate result does not prove point-in-time or provider semantics. It is
never promoted to AVAILABLE here. X6 validation is recalculated against X5.
Neither bridge classifies regimes, votes, or changes trading authority.
"""

from __future__ import annotations

import math
from datetime import datetime

from services.x4.contracts_v1 import X4ResultV1
from services.x5.contracts_v1 import X5ChainCaptureV1
from services.x6.contracts_v1 import X6InputValidationV1, X6VolatilityCaptureV1
from services.x6.input_validation_v1 import validate_x6_input_v1
from services.x7.contracts_v1 import _aware, _sha, _text, canonical_sha256
from services.x8.contracts_v1 import X8EvidenceReferenceV1, require_identity


def _check_available(
    *, observed_at: datetime, available_at: datetime | None, as_of: datetime, budget: float
) -> None:
    if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
        raise ValueError("Positive finite freshness budget required")
    if observed_at > as_of or (
        available_at is not None
        and (not _aware(available_at) or available_at < observed_at or available_at > as_of)
    ):
        raise ValueError("Upstream evidence is future dated or unavailable at capture")


def bind_x4_futures_to_x8_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    result: X4ResultV1,
    expected_result_sha256: str,
    result_available_at: datetime | None,
    max_age_seconds: float,
) -> X8EvidenceReferenceV1:
    require_identity(market, session_id, capture_id, as_of)
    if type(result) is not X4ResultV1:
        raise TypeError("Exact immutable X4 result required")
    if not _sha(expected_result_sha256) or result.sha256() != expected_result_sha256:
        raise ValueError("Detached X4 result hash mismatch")
    if (
        result.market != market
        or result.session_id != session_id
        or not _text(result.instrument_id)
    ):
        raise ValueError("X4 market/session/instrument identity mismatch")
    _check_available(
        observed_at=result.as_of,
        available_at=result_available_at,
        as_of=as_of,
        budget=max_age_seconds,
    )
    age = (as_of - result.as_of).total_seconds()
    state = (
        "UNAVAILABLE"
        if result.status == "UNAVAILABLE"
        else "STALE"
        if age > max_age_seconds
        else "UNVERIFIED"
    )
    # X4 result status alone is not a source-time or provider authenticity proof.
    return X8EvidenceReferenceV1(
        family="FUTURES",
        source_id="X4_FUTURES_RESULT",
        source_record_id=f"{result.instrument_id}:{session_id}:{result.timeframe}:{expected_result_sha256}",
        source_sha256=expected_result_sha256,
        observed_at=result.as_of,
        available_at=result_available_at,
        state=state,
        point_in_time_verified=False,
    )


def bind_x6_volatility_to_x8_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    capture: X6VolatilityCaptureV1,
    source_x5: X5ChainCaptureV1,
    validation: X6InputValidationV1,
    expected_capture_sha256: str,
    expected_x5_sha256: str,
    expected_validation_sha256: str,
    result_available_at: datetime | None,
    max_age_seconds: float,
) -> X8EvidenceReferenceV1:
    require_identity(market, session_id, capture_id, as_of)
    if (
        type(capture) is not X6VolatilityCaptureV1
        or type(source_x5) is not X5ChainCaptureV1
        or type(validation) is not X6InputValidationV1
    ):
        raise TypeError("Exact original immutable X5/X6 contracts required")
    if (
        not all(
            _sha(x)
            for x in (expected_capture_sha256, expected_x5_sha256, expected_validation_sha256)
        )
        or capture.sha256() != expected_capture_sha256
        or source_x5.sha256() != expected_x5_sha256
        or validation.sha256() != expected_validation_sha256
    ):
        raise ValueError("Detached X5/X6 proof hash mismatch")
    if (
        capture.context.market != market
        or capture.session_id != session_id
        or capture.capture_id != capture_id
        or source_x5.session_id != session_id
        or source_x5.capture_id != capture_id
        or validation.source_capture_sha256 != expected_capture_sha256
        or validation.source_x5_capture_sha256 != expected_x5_sha256
    ):
        raise ValueError("X5/X6 market, session, capture or source binding mismatch")
    original = validate_x6_input_v1(capture=capture, source_x5=source_x5)
    if original.sha256() != expected_validation_sha256:
        raise ValueError("X6 validation cannot be reproduced from its original X5/X6 capture")
    _check_available(
        observed_at=capture.context.as_of,
        available_at=result_available_at,
        as_of=as_of,
        budget=max_age_seconds,
    )
    age = (as_of - capture.context.as_of).total_seconds()
    if validation.status == "UNAVAILABLE":
        state = "UNAVAILABLE"
    elif age > max_age_seconds:
        state = "STALE"
    elif result_available_at is None or validation.time_status != "POINT_IN_TIME":
        state = "UNVERIFIED"
    elif validation.status == "PARTIAL":
        state = "PARTIAL"
    else:
        state = "AVAILABLE"
    return X8EvidenceReferenceV1(
        family="VOLATILITY",
        source_id="X6_VOLATILITY_VALIDATION",
        source_record_id=f"{capture_id}:{expected_capture_sha256}",
        source_sha256=canonical_sha256(
            (expected_capture_sha256, expected_x5_sha256, expected_validation_sha256)
        ),
        observed_at=capture.context.as_of,
        available_at=result_available_at,
        state=state,
        point_in_time_verified=state == "AVAILABLE",
    )
