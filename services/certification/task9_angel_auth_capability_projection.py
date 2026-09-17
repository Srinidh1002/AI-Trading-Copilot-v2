"""Projection of sanitized Angel auth readiness into Task 9 provider authority."""
from __future__ import annotations

from dataclasses import replace

from services.certification.task9_angel_auth_session_readiness import (
    Task9AngelAuthReadinessResultV1,
    Task9AngelAuthReadinessStatus,
)
from services.contracts.task9_angel_auth_incident_v1 import (
    Task9AngelAuthIncidentSeverity,
    Task9AngelAuthIncidentV1,
)
from services.contracts.task9_angel_auth_session_proof_v1 import (
    Task9AngelAuthSessionProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderCapability,
    Task9ProviderCapabilityReportV1,
    Task9ProviderCapabilityStateV1,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupSemantic,
)


_AUTH_IDENTITY = (
    Task9ProviderFamily.ANGEL_AUTH_SESSION,
    Task9ProviderCapability.AUTH_SESSION,
    None,
    None,
)


def build_task9_angel_auth_incident(
    *,
    proof: Task9AngelAuthSessionProofV1,
    readiness: Task9AngelAuthReadinessResultV1,
) -> Task9AngelAuthIncidentV1 | None:
    if (
        type(proof)
        is not Task9AngelAuthSessionProofV1
    ):
        raise TypeError("proof")

    if (
        type(readiness)
        is not Task9AngelAuthReadinessResultV1
    ):
        raise TypeError("readiness")

    if readiness.proof_id != proof.proof_id:
        raise ValueError(
            "TASK9_ANGEL_AUTH_PROOF_ID_MISMATCH"
        )

    if (
        readiness.status
        is Task9AngelAuthReadinessStatus.READY
    ):
        return None

    if readiness.reason_code is None:
        raise ValueError(
            "TASK9_ANGEL_AUTH_FAILURE_REASON_MISSING"
        )

    severity = (
        Task9AngelAuthIncidentSeverity.FAILED_FATAL
        if (
            readiness.status
            is Task9AngelAuthReadinessStatus.FAILED_FATAL
        )
        else Task9AngelAuthIncidentSeverity.BLOCKED_RETRYABLE
    )

    incident_id = (
        proof.incident_ref
        or (
            "task9-angel-auth:"
            + proof.proof_id
        )
    )

    return Task9AngelAuthIncidentV1(
        incident_id=incident_id,
        proof_id=proof.proof_id,
        observed_at=proof.observed_at,
        severity=severity,
        reason_code=(
            readiness.reason_code.value
        ),
        provider_code=proof.provider_code,
        sanitized_reason=(
            proof.sanitized_reason
        ),
    )


def project_task9_angel_auth_readiness_to_report(
    *,
    report: Task9ProviderCapabilityReportV1,
    proof: Task9AngelAuthSessionProofV1,
    readiness: Task9AngelAuthReadinessResultV1,
) -> Task9ProviderCapabilityReportV1:
    if (
        type(report)
        is not Task9ProviderCapabilityReportV1
    ):
        raise TypeError("report")

    if (
        type(proof)
        is not Task9AngelAuthSessionProofV1
    ):
        raise TypeError("proof")

    if (
        type(readiness)
        is not Task9AngelAuthReadinessResultV1
    ):
        raise TypeError("readiness")

    if readiness.proof_id != proof.proof_id:
        raise ValueError(
            "TASK9_ANGEL_AUTH_PROOF_ID_MISMATCH"
        )

    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        )
        == _AUTH_IDENTITY
    )

    if len(matches) != 1:
        raise ValueError(
            "TASK9_ANGEL_AUTH_GENERIC_ROW_INVALID"
        )

    current = matches[0]

    incident = build_task9_angel_auth_incident(
        proof=proof,
        readiness=readiness,
    )

    if (
        readiness.status
        is Task9AngelAuthReadinessStatus.READY
    ):
        projected = replace(
            current,
            live_proof_status=(
                Task9LiveProofStatus.PROVEN
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.READY
            ),
            startup_semantic=None,
            evidence_refs=tuple(
                sorted(
                    set(
                        current.evidence_refs
                    )
                    | {
                        "task9-angel-auth-session-proof.v1",
                    }
                )
            ),
            incident_refs=(),
        )

    elif (
        readiness.status
        is Task9AngelAuthReadinessStatus.FAILED_FATAL
    ):
        if incident is None:
            raise ValueError(
                "TASK9_ANGEL_AUTH_INCIDENT_REQUIRED"
            )

        projected = replace(
            current,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            startup_semantic=(
                Task9StartupSemantic.STARTUP_FATAL
            ),
            evidence_refs=tuple(
                sorted(
                    set(
                        current.evidence_refs
                    )
                    | {
                        "task9-angel-auth-session-proof.v1",
                    }
                )
            ),
            incident_refs=tuple(
                sorted(
                    set(
                        current.incident_refs
                    )
                    | {
                        incident.incident_id,
                    }
                )
            ),
        )

    else:
        if incident is None:
            raise ValueError(
                "TASK9_ANGEL_AUTH_INCIDENT_REQUIRED"
            )

        projected = replace(
            current,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            startup_semantic=(
                Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE
            ),
            evidence_refs=tuple(
                sorted(
                    set(
                        current.evidence_refs
                    )
                    | {
                        "task9-angel-auth-session-proof.v1",
                    }
                )
            ),
            incident_refs=tuple(
                sorted(
                    set(
                        current.incident_refs
                    )
                    | {
                        incident.incident_id,
                    }
                )
            ),
        )

    rows: list[
        Task9ProviderCapabilityStateV1
    ] = []

    replaced = False

    for state in report.capability_states:
        identity = (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        )

        if identity == _AUTH_IDENTITY:
            rows.append(projected)
            replaced = True
        else:
            rows.append(state)

    if not replaced:
        raise ValueError(
            "TASK9_ANGEL_AUTH_GENERIC_ROW_MISSING"
        )

    return Task9ProviderCapabilityReportV1(
        runtime_config_id=(
            report.runtime_config_id
        ),
        runtime_config_version=(
            report.runtime_config_version
        ),
        capability_states=tuple(rows),
    )
