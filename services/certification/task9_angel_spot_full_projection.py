"""Project per-market Angel spot FULL readiness into Task 9 provider report."""
from __future__ import annotations

from dataclasses import replace

from services.certification.task9_angel_spot_full_readiness import (
    Task9AngelSpotFullReadinessStatus,
    Task9AngelSpotFullReadinessV1,
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


def project_task9_angel_spot_full_to_report(
    *,
    report: Task9ProviderCapabilityReportV1,
    readiness: Task9AngelSpotFullReadinessV1,
) -> Task9ProviderCapabilityReportV1:
    if (
        type(report)
        is not Task9ProviderCapabilityReportV1
    ):
        raise TypeError("report")

    if (
        type(readiness)
        is not Task9AngelSpotFullReadinessV1
    ):
        raise TypeError("readiness")

    identity = (
        Task9ProviderFamily.ANGEL_SPOT,
        Task9ProviderCapability.SPOT_QUOTES,
        readiness.market,
        readiness.exchange,
    )

    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        ) == identity
    )

    if len(matches) != 1:
        raise ValueError(
            "TASK9_ANGEL_SPOT_GENERIC_ROW_INVALID"
        )

    current = matches[0]

    evidence_refs = tuple(
        sorted(
            set(current.evidence_refs)
            | {
                "task9-angel-spot-full-proof.v1",
            }
        )
    )

    incident_refs = (
        ()
        if readiness.incident_ref is None
        else tuple(
            sorted(
                set(current.incident_refs)
                | {
                    readiness.incident_ref,
                }
            )
        )
    )

    metadata = dict(current.metadata)

    metadata[
        "quote_max_age_seconds"
    ] = readiness.maximum_quote_age_seconds

    if readiness.quote_age_seconds is not None:
        metadata[
            "quote_age_seconds"
        ] = readiness.quote_age_seconds

    metadata[
        "spot_instrument_id"
    ] = readiness.token

    if (
        readiness.status
        is Task9AngelSpotFullReadinessStatus.READY
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
            evidence_refs=evidence_refs,
            incident_refs=(),
            metadata=metadata,
        )

    elif (
        readiness.status
        is Task9AngelSpotFullReadinessStatus.FAILED_FATAL
    ):
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
            evidence_refs=evidence_refs,
            incident_refs=incident_refs,
            metadata=metadata,
        )

    else:
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
            evidence_refs=evidence_refs,
            incident_refs=incident_refs,
            metadata=metadata,
        )

    rows: list[
        Task9ProviderCapabilityStateV1
    ] = []

    replaced = False

    for state in report.capability_states:
        state_identity = (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        )

        if state_identity == identity:
            rows.append(projected)
            replaced = True
        else:
            rows.append(state)

    if not replaced:
        raise ValueError(
            "TASK9_ANGEL_SPOT_GENERIC_ROW_MISSING"
        )

    return Task9ProviderCapabilityReportV1(
        runtime_config_id=report.runtime_config_id,
        runtime_config_version=(
            report.runtime_config_version
        ),
        capability_states=tuple(rows),
    )
