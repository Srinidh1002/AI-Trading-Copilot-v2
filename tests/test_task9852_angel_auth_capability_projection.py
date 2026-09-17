from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_angel_auth_capability_projection import (
    build_task9_angel_auth_incident,
    project_task9_angel_auth_readiness_to_report,
)
from services.certification.task9_angel_auth_session_readiness import (
    Task9AngelAuthReadinessStatus,
    evaluate_task9_angel_auth_session,
)
from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.certification.task9_runtime_config_builder import (
    build_task9_runtime_config,
)
from services.contracts.task9_angel_auth_incident_v1 import (
    Task9AngelAuthIncidentSeverity,
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
    Task9ProviderCapability,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupSemantic,
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


def _runtime():
    return build_task9_runtime_config(
        runtime_config_id="task9852-runtime",
        runtime_config_version="1",
        campaign_registry_location="task9852/campaign.json",
        campaign_id="task9852-campaign",
        market_date=date(2026, 8, 17),
        official_run_id="task9852-run",
        official_root="task9852/official",
        certification_registry_root="task9852/registry",
        authoritative_persistence_root="task9852/persistence",
        dashboard_publication_location="task9852/dashboard.json",
        available_capital=100000.0,
        risk_fraction=0.02,
        maximum_quantity=100,
        policy_references={
            "canonical_directional": "task9852-canonical.v1",
            "session": "task9852-session.v1",
            "risk": "task9852-risk.v1",
            "contract_selection": "task9852-contract.v1",
            "lifecycle": "task9852-lifecycle.v1",
            "counting": "task9852-counting.v1",
            "failure_disposition": "task9852-failure.v1",
            "contract_spread": "task9852-spread.v1",
            "liquidity": "task9852-liquidity.v1",
            "minimum_risk_reward": "task9852-rr.v1",
            "stop_target": "task9852-stop-target.v1",
            "portfolio_concurrency": "task9852-concurrency.v1",
        },
    )


def _report():
    return build_task9_provider_capability_report(
        _runtime()
    )


def _authority():
    return build_task9_angel_capability_session()


def _proof(
    *,
    status=Task9AngelAuthProbeStatus.READY,
    code=None,
    reason=None,
    refs=True,
):
    return Task9AngelAuthSessionProofV1(
        proof_id=(
            "task9852-proof-"
            + (
                code.lower()
                if code
                else status.value.lower()
            )
        ),
        observed_at=NOW,
        status=status,
        credential_references_present=refs,
        credential_kinds_confirmed=(
            CREDENTIALS
            if status
            is Task9AngelAuthProbeStatus.READY
            else ()
        ),
        provider_code=code,
        sanitized_reason=reason,
        incident_ref=(
            None
            if status
            is Task9AngelAuthProbeStatus.READY
            else "incident-task9852-auth"
        ),
    )


def _auth_row(report):
    matches = [
        state
        for state in report.capability_states
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_AUTH_SESSION
            and state.capability
            is Task9ProviderCapability.AUTH_SESSION
        )
    ]

    assert len(matches) == 1
    return matches[0]


def test_ready_projection_marks_only_auth_row_ready():
    report = _report()
    proof = _proof()

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    projected = (
        project_task9_angel_auth_readiness_to_report(
            report=report,
            proof=proof,
            readiness=readiness,
        )
    )

    row = _auth_row(projected)

    assert (
        row.live_proof_status
        is Task9LiveProofStatus.PROVEN
    )
    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.READY
    )
    assert row.startup_semantic is None
    assert row.incident_refs == ()

    original_others = tuple(
        state
        for state in report.capability_states
        if state is not _auth_row(report)
    )

    projected_others = tuple(
        state
        for state in projected.capability_states
        if state is not row
    )

    assert projected_others == original_others


def test_retryable_projection_blocks_auth_row():
    proof = _proof(
        status=Task9AngelAuthProbeStatus.FAILED,
        code="AG8002",
        reason="SANITIZED_AUTH_RETRYABLE",
    )

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    projected = (
        project_task9_angel_auth_readiness_to_report(
            report=_report(),
            proof=proof,
            readiness=readiness,
        )
    )

    row = _auth_row(projected)

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
    )
    assert (
        row.startup_semantic
        is Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE
    )
    assert row.incident_refs == (
        "incident-task9852-auth",
    )


def test_fatal_projection_marks_auth_row_fatal():
    proof = _proof(
        status=Task9AngelAuthProbeStatus.FAILED,
        code="AG8001",
        reason="SANITIZED_AUTH_FATAL",
    )

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    projected = (
        project_task9_angel_auth_readiness_to_report(
            report=_report(),
            proof=proof,
            readiness=readiness,
        )
    )

    row = _auth_row(projected)

    assert (
        row.readiness_status
        is Task9ProviderReadinessStatus.FAILED_FATAL
    )
    assert (
        row.startup_semantic
        is Task9StartupSemantic.STARTUP_FATAL
    )


def test_missing_credentials_project_fatal():
    proof = _proof(
        status=Task9AngelAuthProbeStatus.FAILED,
        reason="MISSING_REQUIRED_CREDENTIAL_REFERENCE",
        refs=False,
    )

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    projected = (
        project_task9_angel_auth_readiness_to_report(
            report=_report(),
            proof=proof,
            readiness=readiness,
        )
    )

    assert (
        _auth_row(projected).readiness_status
        is Task9ProviderReadinessStatus.FAILED_FATAL
    )


def test_success_produces_no_incident():
    proof = _proof()

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    assert (
        build_task9_angel_auth_incident(
            proof=proof,
            readiness=readiness,
        )
        is None
    )


def test_retryable_incident_is_sanitized():
    proof = _proof(
        status=Task9AngelAuthProbeStatus.FAILED,
        code="AB1011",
        reason="SANITIZED_SESSION_FAILURE",
    )

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    incident = build_task9_angel_auth_incident(
        proof=proof,
        readiness=readiness,
    )

    assert incident is not None

    assert (
        incident.severity
        is Task9AngelAuthIncidentSeverity.BLOCKED_RETRYABLE
    )
    assert incident.reason_code == "AB1011"
    assert incident.provider_code == "AB1011"

    raw = repr(
        incident.to_dict()
    ).lower()

    for forbidden in (
        "api_key",
        "password",
        "authorization",
        "totp",
        "raw_exception",
    ):
        assert forbidden not in raw


def test_fatal_incident_is_sanitized():
    proof = _proof(
        status=Task9AngelAuthProbeStatus.FAILED,
        code="AB8050",
        reason="SANITIZED_FATAL_AUTH_FAILURE",
    )

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    incident = build_task9_angel_auth_incident(
        proof=proof,
        readiness=readiness,
    )

    assert incident is not None

    assert (
        incident.severity
        is Task9AngelAuthIncidentSeverity.FAILED_FATAL
    )


def test_projection_is_deterministic_and_idempotent():
    proof = _proof(
        status=Task9AngelAuthProbeStatus.FAILED,
        code="AB1010",
        reason="SANITIZED_TEMPORARY_FAILURE",
    )

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    first = (
        project_task9_angel_auth_readiness_to_report(
            report=_report(),
            proof=proof,
            readiness=readiness,
        )
    )

    second = (
        project_task9_angel_auth_readiness_to_report(
            report=first,
            proof=proof,
            readiness=readiness,
        )
    )

    assert first.to_dict() == second.to_dict()


def test_mismatched_proof_identity_fails_closed():
    proof = _proof(
        status=Task9AngelAuthProbeStatus.FAILED,
        code="AB1011",
        reason="SANITIZED_FAILURE",
    )

    other = Task9AngelAuthSessionProofV1(
        proof_id="different-proof",
        observed_at=NOW,
        status=Task9AngelAuthProbeStatus.FAILED,
        credential_references_present=True,
        credential_kinds_confirmed=(),
        provider_code="AB1011",
        sanitized_reason="SANITIZED_FAILURE",
        incident_ref="incident-other",
    )

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    with pytest.raises(
        ValueError,
        match="PROOF_ID_MISMATCH",
    ):
        project_task9_angel_auth_readiness_to_report(
            report=_report(),
            proof=other,
            readiness=readiness,
        )


def test_wrong_types_fail_closed():
    proof = _proof()

    readiness = evaluate_task9_angel_auth_session(
        authority=_authority(),
        proof=proof,
    )

    with pytest.raises(TypeError):
        project_task9_angel_auth_readiness_to_report(
            report=object(),
            proof=proof,
            readiness=readiness,
        )

    with pytest.raises(TypeError):
        build_task9_angel_auth_incident(
            proof=object(),
            readiness=readiness,
        )
