"""Task 9 WebSocket runtime readiness and generic capability projection."""
from __future__ import annotations

from dataclasses import replace

from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderCapability,
    Task9ProviderCapabilityReportV1,
    Task9ProviderCapabilityStateV1,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
)
from services.contracts.task9_websocket_runtime_proof_v1 import (
    Task9WebsocketRuntimeProbeStatus,
    Task9WebsocketRuntimeProofV1,
)


_IDENTITY = (
    Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET,
    Task9ProviderCapability.MARKET_DATA_WEBSOCKET,
    None,
    None,
)


def project_task9_websocket_runtime_to_report(
    *,
    report: Task9ProviderCapabilityReportV1,
    proof: Task9WebsocketRuntimeProofV1,
) -> Task9ProviderCapabilityReportV1:
    if type(report) is not Task9ProviderCapabilityReportV1:
        raise TypeError("report")

    if type(proof) is not Task9WebsocketRuntimeProofV1:
        raise TypeError("proof")

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
            "TASK9_WEBSOCKET_GENERIC_ROW_INVALID"
        )

    current = matches[0]

    metadata = dict(
        current.metadata
    )

    metadata.update({
        "collector_lock_present": (
            proof.collector_lock_present
        ),
        "collector_lock_valid": (
            proof.collector_lock_valid
        ),
        "maximum_tick_age_seconds": (
            proof.maximum_tick_age_seconds
        ),
        "nifty_tick_received_at": (
            proof.nifty_tick_received_at.isoformat()
            if proof.nifty_tick_received_at
            else None
        ),
        "sensex_tick_received_at": (
            proof.sensex_tick_received_at.isoformat()
            if proof.sensex_tick_received_at
            else None
        ),
    })

    evidence_refs = tuple(
        sorted(
            set(current.evidence_refs)
            | {
                "task9-websocket-runtime-proof.v1",
            }
        )
    )

    ready = (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.READY
    )

    # Generic provider capability metadata is deliberately scalar-only.
    # Missing durable WebSocket observations are represented by absence,
    # never by a None metadata value.
    metadata = {
        key: value
        for key, value in metadata.items()
        if value is not None
    }

    projected = replace(
        current,
        live_proof_status=(
            Task9LiveProofStatus.PROVEN
            if ready
            else Task9LiveProofStatus.PENDING
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY
            if ready
            else Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
        ),
        startup_semantic=(
            None
            if ready
            else current.startup_semantic
        ),
        evidence_refs=evidence_refs,
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

        rows.append(
            projected
            if identity == _IDENTITY
            else state
        )

    return Task9ProviderCapabilityReportV1(
        runtime_config_id=report.runtime_config_id,
        runtime_config_version=(
            report.runtime_config_version
        ),
        capability_states=tuple(rows),
    )


def build_task9_collector_runtime_preflight_phase(
    *,
    proof: Task9WebsocketRuntimeProofV1,
) -> Task9StartupPreflightPhaseResultV1:
    if type(proof) is not Task9WebsocketRuntimeProofV1:
        raise TypeError("proof")

    if (
        proof.status
        is Task9WebsocketRuntimeProbeStatus.READY
    ):
        return Task9StartupPreflightPhaseResultV1(
            phase=(
                Task9StartupPreflightPhase.COLLECTOR_RUNTIME_READINESS
            ),
            status=(
                Task9StartupPreflightPhaseStatus.PASS
            ),
            blocking=False,
            reason_code=(
                "COLLECTOR_RUNTIME_READY"
            ),
            detail=None,
            observed_at=proof.observed_at,
        )

    return Task9StartupPreflightPhaseResultV1(
        phase=(
            Task9StartupPreflightPhase.COLLECTOR_RUNTIME_READINESS
        ),
        status=(
            Task9StartupPreflightPhaseStatus.BLOCKED
        ),
        blocking=True,
        reason_code="COLLECTOR_NOT_READY",
        detail=proof.sanitized_reason,
        observed_at=proof.observed_at,
    )


__all__ = (
    "build_task9_collector_runtime_preflight_phase",
    "project_task9_websocket_runtime_to_report",
)
