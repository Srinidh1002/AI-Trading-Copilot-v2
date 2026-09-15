"""Project Task 9 persistence proof into startup preflight."""
from __future__ import annotations

from services.contracts.task9_persistence_writability_proof_v1 import (
    Task9PersistenceProbeStatus,
    Task9PersistenceWritabilityProofV1,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
)


def build_task9_persistence_writability_preflight_phase(
    *,
    proof: Task9PersistenceWritabilityProofV1,
) -> Task9StartupPreflightPhaseResultV1:
    if (
        type(proof)
        is not Task9PersistenceWritabilityProofV1
    ):
        raise TypeError("proof")

    ready = (
        proof.status
        is Task9PersistenceProbeStatus.READY
    )

    return Task9StartupPreflightPhaseResultV1(
        phase=(
            Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY
        ),
        status=(
            Task9StartupPreflightPhaseStatus.PASS
            if ready
            else Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE
        ),
        blocking=not ready,
        reason_code=(
            "PERSISTENCE_INTEGRITY_WRITABLE"
            if ready
            else "PERSISTENCE_INTEGRITY_NOT_WRITABLE"
        ),
        detail=(
            None
            if ready
            else proof.sanitized_reason
        ),
        observed_at=proof.observed_at,
    )


__all__ = (
    "build_task9_persistence_writability_preflight_phase",
)
