"""Project Angel Greeks capability state into Task 9 provider report."""
from __future__ import annotations

from dataclasses import replace

from services.certification.task9_angel_greeks_readiness import (
    Task9AngelGreeksReadinessStatus,
    Task9AngelGreeksReadinessV1,
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


def project_task9_angel_greeks_to_report(
    *,
    report: Task9ProviderCapabilityReportV1,
    readiness: Task9AngelGreeksReadinessV1,
) -> Task9ProviderCapabilityReportV1:
    if (
        type(report)
        is not Task9ProviderCapabilityReportV1
    ):
        raise TypeError("report")

    if (
        type(readiness)
        is not Task9AngelGreeksReadinessV1
    ):
        raise TypeError("readiness")

    identity = (
        Task9ProviderFamily.ANGEL_OPTION_GREEKS,
        Task9ProviderCapability.OPTION_GREEKS,
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
            "TASK9_ANGEL_GREEKS_GENERIC_ROW_INVALID"
        )

    current = matches[0]

    metadata = dict(
        current.metadata
    )

    metadata.update({
        "requested_contract_count": (
            readiness.requested_contract_count
        ),
        "enriched_contract_count": (
            readiness.enriched_contract_count
        ),
        "unavailable_contract_count": (
            readiness.unavailable_contract_count
        ),
        "partial_response": (
            readiness.partial_response
        ),
    })

    evidence_refs = tuple(
        sorted(
            set(current.evidence_refs)
            | {
                "task9-angel-greeks-proof.v1",
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
        is Task9AngelGreeksReadinessStatus.READY
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
            incident_refs=incident_refs,
            metadata=metadata,
        )

    elif (
        readiness.status
        is Task9AngelGreeksReadinessStatus.UNSUPPORTED
    ):
        projected = replace(
            current,
            live_proof_status=(
                Task9LiveProofStatus.NOT_APPLICABLE
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.UNSUPPORTED
            ),
            startup_semantic=(
                Task9StartupSemantic.OPTIONAL_UNAVAILABLE
            ),
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
            "TASK9_ANGEL_GREEKS_GENERIC_ROW_MISSING"
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
