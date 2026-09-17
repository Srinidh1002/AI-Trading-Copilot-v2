from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_auth_session_readiness import (
    Task9AngelAuthReadinessStatus,
    evaluate_task9_angel_auth_session,
)
from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.contracts.task9_angel_auth_session_proof_v1 import (
    Task9AngelAuthProbeStatus,
    Task9AngelAuthSessionProofV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelSessionCredentialKind,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupReasonCode,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    9,
    0,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)

CREDENTIALS = (
    Task9AngelSessionCredentialKind.JWT,
    Task9AngelSessionCredentialKind.REFRESH,
    Task9AngelSessionCredentialKind.FEED,
)


def _authority():
    return build_task9_angel_capability_session()


def _ready():
    return Task9AngelAuthSessionProofV1(
        proof_id="task9852-auth-ready",
        observed_at=NOW,
        status=Task9AngelAuthProbeStatus.READY,
        credential_references_present=True,
        credential_kinds_confirmed=CREDENTIALS,
    )


def _failed(
    code=None,
    *,
    credential_references_present=True,
    reason="SANITIZED_PROVIDER_FAILURE",
):
    return Task9AngelAuthSessionProofV1(
        proof_id=(
            "task9852-auth-failed-"
            + (code or "unknown")
        ),
        observed_at=NOW,
        status=Task9AngelAuthProbeStatus.FAILED,
        credential_references_present=(
            credential_references_present
        ),
        credential_kinds_confirmed=(),
        provider_code=code,
        sanitized_reason=reason,
        incident_ref="incident-task9852-auth",
    )


def test_ready_session_proves_live_auth_capability():
    result = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=_ready(),
    )

    assert (
        result.status
        is Task9AngelAuthReadinessStatus.READY
    )
    assert (
        result.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert result.reason_code is None

    assert (
        result.phase_result.phase
        is Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION
    )
    assert (
        result.phase_result.status
        is Task9StartupPreflightPhaseStatus.PASS
    )
    assert result.phase_result.blocking is False


def test_missing_credential_reference_is_fatal():
    result = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=_failed(
            None,
            credential_references_present=False,
            reason="MISSING_REQUIRED_CREDENTIAL_REFERENCE",
        ),
    )

    assert (
        result.status
        is Task9AngelAuthReadinessStatus.FAILED_FATAL
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.MISSING_CREDENTIAL_REFERENCE
    )
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.FAILED_FATAL
    )
    assert result.phase_result.blocking is True


@pytest.mark.parametrize(
    "code",
    (
        "AG8001",
        "AG8003",
        "AB8050",
    ),
)
def test_canonical_fatal_provider_codes(code):
    result = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=_failed(code),
    )

    assert (
        result.status
        is Task9AngelAuthReadinessStatus.FAILED_FATAL
    )
    assert result.reason_code.value == code
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.FAILED_FATAL
    )
    assert result.phase_result.blocking is True


@pytest.mark.parametrize(
    "code",
    (
        "AG8002",
        "AB8051",
        "AB1010",
        "AB1011",
        "AB2001",
    ),
)
def test_canonical_retryable_provider_codes(code):
    result = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=_failed(code),
    )

    assert (
        result.status
        is Task9AngelAuthReadinessStatus.BLOCKED_RETRYABLE
    )
    assert result.reason_code.value == code
    assert (
        result.readiness_status
        is Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
    )
    assert result.phase_result.blocking is True


def test_unknown_provider_code_fails_closed_retryable():
    result = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=_failed("AB9999"),
    )

    assert (
        result.status
        is Task9AngelAuthReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
    )


def test_failure_without_provider_code_is_retryable():
    result = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=_failed(
            None,
            reason="SANITIZED_NETWORK_OR_SESSION_FAILURE",
        ),
    )

    assert (
        result.status
        is Task9AngelAuthReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        result.reason_code
        is Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
    )


@pytest.mark.parametrize(
    "field_value",
    (
        "jwt=abcdef",
        "refresh_token=abcdef",
        "feed_token=abcdef",
        "api_key=abcdef",
        "password=abcdef",
        "totp=123456",
        "authorization=Bearer-abc",
        "raw_exception=boom",
    ),
)
def test_secret_like_reason_is_rejected(field_value):
    with pytest.raises(
        ValueError,
        match="secret-like",
    ):
        Task9AngelAuthSessionProofV1(
            proof_id="task9852-secret-reject",
            observed_at=NOW,
            status=Task9AngelAuthProbeStatus.FAILED,
            credential_references_present=True,
            credential_kinds_confirmed=(),
            sanitized_reason=field_value,
        )


def test_serialized_proof_contains_no_secret_values():
    raw = repr(
        _ready().to_dict()
    ).lower()

    for forbidden in (
        "api_key",
        "password",
        "authorization",
        "totp",
        "refresh_token",
        "feed_token",
        "access_token",
    ):
        assert forbidden not in raw


def test_ready_cannot_claim_partial_session_credentials():
    with pytest.raises(
        ValueError,
        match="JWT/REFRESH/FEED",
    ):
        Task9AngelAuthSessionProofV1(
            proof_id="task9852-partial",
            observed_at=NOW,
            status=Task9AngelAuthProbeStatus.READY,
            credential_references_present=True,
            credential_kinds_confirmed=(
                Task9AngelSessionCredentialKind.JWT,
                Task9AngelSessionCredentialKind.REFRESH,
            ),
        )


def test_paper_safety_is_immutable():
    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9AngelAuthSessionProofV1(
            proof_id="task9852-unsafe",
            observed_at=NOW,
            status=Task9AngelAuthProbeStatus.READY,
            credential_references_present=True,
            credential_kinds_confirmed=CREDENTIALS,
            broker_order_submission=True,
        )


def test_wrong_types_fail_closed():
    with pytest.raises(TypeError):
        evaluate_task9_angel_auth_session(
            authority=object(),
            proof=_ready(),
        )

    with pytest.raises(TypeError):
        evaluate_task9_angel_auth_session(
            authority=_authority(),
            proof=object(),
        )
