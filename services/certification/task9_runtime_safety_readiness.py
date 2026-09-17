"""Task 9 runtime safety -> canonical PAPER_SAFETY preflight phase."""
from __future__ import annotations

from services.contracts.task9_runtime_safety_proof_v1 import (
    Task9RuntimeSafetyProofV1,
    Task9RuntimeSafetyStatus,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
)


def build_task9_runtime_safety_preflight_phase(
    *,
    proof: Task9RuntimeSafetyProofV1,
) -> Task9StartupPreflightPhaseResultV1:
    if (
        type(proof)
        is not Task9RuntimeSafetyProofV1
    ):
        raise TypeError(
            "proof"
        )

    if (
        proof.status
        is Task9RuntimeSafetyStatus.READY
    ):
        return Task9StartupPreflightPhaseResultV1(
            phase=(
                Task9StartupPreflightPhase.PAPER_SAFETY
            ),
            status=(
                Task9StartupPreflightPhaseStatus.PASS
            ),
            blocking=False,
            reason_code=(
                "TASK9_PAPER_RUNTIME_SAFETY_READY"
            ),
            detail=None,
            observed_at=proof.observed_at,
            metadata={
                "new_entries_permitted": True,
                "monitoring_permitted": True,
            },
        )

    if (
        proof.status
        is Task9RuntimeSafetyStatus.EMERGENCY_HALTED
    ):
        return Task9StartupPreflightPhaseResultV1(
            phase=(
                Task9StartupPreflightPhase.PAPER_SAFETY
            ),
            status=(
                Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE
            ),
            blocking=True,
            reason_code=(
                "TASK9_EMERGENCY_HALT_ACTIVE"
            ),
            detail=(
                "Emergency halt is active; "
                "new Task 9 PAPER entries are suppressed."
            ),
            observed_at=proof.observed_at,
            metadata={
                "new_entries_permitted": False,
                "monitoring_permitted": True,
            },
        )

    return Task9StartupPreflightPhaseResultV1(
        phase=(
            Task9StartupPreflightPhase.PAPER_SAFETY
        ),
        status=(
            Task9StartupPreflightPhaseStatus.FAIL_FATAL
        ),
        blocking=True,
        reason_code=(
            "TASK9_PAPER_RUNTIME_SAFETY_INVALID"
        ),
        detail=(
            proof.sanitized_reason
        ),
        observed_at=proof.observed_at,
        metadata={
            "new_entries_permitted": False,
            "monitoring_permitted": True,
        },
    )


__all__ = (
    "build_task9_runtime_safety_preflight_phase",
)
