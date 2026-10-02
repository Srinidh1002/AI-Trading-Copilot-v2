"""X8-B4 typed X3 technical and X2 manifest boundaries; zero authority.

An X2 feature manifest is a declaration, not measured breadth. X3's result
hash and even VALID features do not attest source publication/availability.
Consequently neither bridge can promote itself into PIT-verified AVAILABLE.
"""

from __future__ import annotations

import math
from datetime import datetime

from services.x7.contracts_v1 import _aware, _sha, canonical_sha256
from services.x8.contracts_v1 import X8EvidenceReferenceV1, require_identity


def bind_x3_technical_to_x8_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    result: object,
    expected_result_sha256: str,
    result_available_at: datetime | None,
    max_age_seconds: float,
) -> X8EvidenceReferenceV1:
    """Check exact X3 MTF shape and digest; preserve unproven publication."""
    from services.x3.contracts_v1 import X3MultiTimeframeResultV1

    require_identity(market, session_id, capture_id, as_of)
    if type(result) is not X3MultiTimeframeResultV1:
        raise TypeError("Exact X3MultiTimeframeResultV1 required")
    if not _sha(expected_result_sha256) or result.sha256 != expected_result_sha256:
        raise ValueError("X3 original-result SHA-256 mismatch")
    if result.market != market or not result.instrument_id:
        raise ValueError("X3 market/instrument mismatch")
    if (
        type(max_age_seconds) not in (int, float)
        or not math.isfinite(max_age_seconds)
        or max_age_seconds <= 0
    ):
        raise ValueError("Positive finite maximum observation age required")
    if result.as_of > as_of or any(
        r.as_of > as_of or any(f.observed_at > as_of for f in r.features)
        for r in result.timeframe_results
    ):
        raise ValueError("Future technical evidence is not admissible")
    if result_available_at is not None and (
        not _aware(result_available_at)
        or result_available_at < result.as_of
        or result_available_at > as_of
    ):
        raise ValueError("Invalid/future technical availability claim")
    if any(
        f.market != market or f.instrument_id != result.instrument_id
        for r in result.timeframe_results
        for f in r.features
    ):
        raise ValueError("Mixed-market X3 technical evidence")
    state = (
        "UNAVAILABLE"
        if not result.timeframe_results
        else "STALE"
        if (as_of - result.as_of).total_seconds() > max_age_seconds
        else "UNVERIFIED"
    )
    return X8EvidenceReferenceV1(
        family="TECHNICAL",
        source_id="X3_MTF_RESULT",
        source_record_id=f"{result.instrument_id}:{result.sha256}",
        source_sha256=expected_result_sha256,
        observed_at=result.as_of,
        available_at=result_available_at,
        state=state,
        point_in_time_verified=False,
    )


def bind_x2_manifest_to_x8_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    manifest: object | None,
    expected_manifest_sha256: str | None,
    observed_at: datetime,
    available_at: datetime | None,
) -> X8EvidenceReferenceV1:
    """Index-only X2 *schema* reference, never observed breadth evidence."""
    from services.x2.feature_manifest_v1 import X2FeatureManifestV1

    require_identity(market, session_id, capture_id, as_of)
    if not _aware(observed_at) or observed_at > as_of:
        raise ValueError("Invalid or future X2 manifest observation time")
    if available_at is not None and (
        not _aware(available_at) or available_at < observed_at or available_at > as_of
    ):
        raise ValueError("Invalid or future X2 manifest availability time")
    if market not in ("NIFTY", "SENSEX"):
        if manifest is not None or expected_manifest_sha256 is not None:
            raise ValueError("X2 constituents are not a verified MCX research source")
        return X8EvidenceReferenceV1(
            family="BREADTH",
            source_id="X2_NOT_APPLICABLE_MCX",
            source_record_id=f"{market}:{session_id}:{capture_id}:X2_UNAVAILABLE",
            source_sha256=canonical_sha256((market, session_id, capture_id, "X2_UNAVAILABLE")),
            observed_at=observed_at,
            available_at=available_at,
            state="UNAVAILABLE",
            point_in_time_verified=False,
        )
    if type(manifest) is not X2FeatureManifestV1:
        raise TypeError("Exact X2FeatureManifestV1 required for index reference")
    if not _sha(expected_manifest_sha256) or manifest.manifest_sha256() != expected_manifest_sha256:
        raise ValueError("X2 feature manifest hash mismatch")
    # The manifest has no measured as-of constituent returns, source timestamps,
    # or quality evidence. Its presence does not establish observed breadth.
    return X8EvidenceReferenceV1(
        family="BREADTH",
        source_id="X2_FEATURE_MANIFEST",
        source_record_id=f"{market}:{expected_manifest_sha256}",
        source_sha256=expected_manifest_sha256,
        observed_at=observed_at,
        available_at=available_at,
        state="UNVERIFIED",
        point_in_time_verified=False,
    )
