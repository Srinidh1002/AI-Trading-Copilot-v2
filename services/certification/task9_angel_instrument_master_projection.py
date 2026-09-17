"""Project Angel instrument-master readiness into generic Task 9 provider report."""
from __future__ import annotations

from dataclasses import replace

from services.certification.task9_angel_instrument_master_readiness import (
    Task9AngelInstrumentMasterReadinessStatus,
    Task9AngelInstrumentMasterReadinessV1,
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
    Task9ProviderFamily.ANGEL_INSTRUMENT_MASTER,
    Task9ProviderCapability.INSTRUMENT_MASTER,
    None,
    None,
)


def project_task9_angel_instrument_master_to_report(
    *,
    report: Task9ProviderCapabilityReportV1,
    readiness: Task9AngelInstrumentMasterReadinessV1,
) -> Task9ProviderCapabilityReportV1:
    if (
        type(report)
        is not Task9ProviderCapabilityReportV1
    ):
        raise TypeError("report")

    if (
        type(readiness)
        is not Task9AngelInstrumentMasterReadinessV1
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
        )
        == _IDENTITY
    )

    if len(matches) != 1:
        raise ValueError(
            "TASK9_INSTRUMENT_MASTER_GENERIC_ROW_INVALID"
        )

    current = matches[0]

    evidence_refs = tuple(
        sorted(
            set(current.evidence_refs)
            | {
                "task9-angel-instrument-master-proof.v1",
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

    metadata = dict(
        current.metadata
    )
    metadata[
        "instrument_master_max_age_seconds"
    ] = readiness.maximum_age_seconds

    if readiness.age_seconds is not None:
        metadata[
            "instrument_master_age_seconds"
        ] = readiness.age_seconds

    if (
        readiness.status
        is Task9AngelInstrumentMasterReadinessStatus.READY
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
        is Task9AngelInstrumentMasterReadinessStatus.FAILED_FATAL
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

    for state in report.capability_states:
        if (
            state.provider_family,
            state.capability,
            state.market,
            state.exchange,
        ) == _IDENTITY:
            rows.append(projected)
        else:
            rows.append(state)

    return Task9ProviderCapabilityReportV1(
        runtime_config_id=report.runtime_config_id,
        runtime_config_version=(
            report.runtime_config_version
        ),
        capability_states=tuple(rows),
    )
