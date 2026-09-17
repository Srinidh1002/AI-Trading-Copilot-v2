"""Project optional Angel India VIX readiness into Task 9 provider report."""
from __future__ import annotations

from dataclasses import replace

from services.certification.task9_angel_india_vix_readiness import (
    Task9AngelIndiaVixReadinessStatus,
    Task9AngelIndiaVixReadinessV1,
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


_IDENTITY = (
    Task9ProviderFamily.INDIA_VIX,
    Task9ProviderCapability.INDIA_VIX,
    None,
    None,
)


def project_task9_angel_india_vix_to_report(
    *,
    report: Task9ProviderCapabilityReportV1,
    readiness: Task9AngelIndiaVixReadinessV1,
) -> Task9ProviderCapabilityReportV1:
    if (
        type(report)
        is not Task9ProviderCapabilityReportV1
    ):
        raise TypeError("report")

    if (
        type(readiness)
        is not Task9AngelIndiaVixReadinessV1
    ):
        raise TypeError("readiness")

    matches = tuple(
        state
        for state in report.capability_states
        if (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        ) == _IDENTITY
    )

    if len(matches) != 1:
        raise ValueError(
            "TASK9_INDIA_VIX_GENERIC_ROW_INVALID"
        )

    current = matches[0]

    metadata = dict(
        current.metadata
    )

    metadata[
        "quote_max_age_seconds"
    ] = readiness.maximum_quote_age_seconds

    metadata[
        "identity_verified"
    ] = readiness.identity_verified

    if readiness.quote_age_seconds is not None:
        metadata[
            "quote_age_seconds"
        ] = readiness.quote_age_seconds

    evidence_refs = tuple(
        sorted(
            set(current.evidence_refs)
            | {
                "task9-angel-india-vix-proof.v1",
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

    if (
        readiness.status
        is Task9AngelIndiaVixReadinessStatus.READY
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

    else:
        projected = replace(
            current,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
            ),
            startup_semantic=(
                Task9StartupSemantic.OPTIONAL_UNAVAILABLE
            ),
            evidence_refs=evidence_refs,
            incident_refs=incident_refs,
            metadata=metadata,
        )

    rows: list[
        Task9ProviderCapabilityStateV1
    ] = []

    for state in report.capability_states:
        identity = (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        )

        if identity == _IDENTITY:
            rows.append(projected)
        else:
            rows.append(state)

    return Task9ProviderCapabilityReportV1(
        runtime_config_id=(
            report.runtime_config_id
        ),
        runtime_config_version=(
            report.runtime_config_version
        ),
        capability_states=tuple(rows),
    )
