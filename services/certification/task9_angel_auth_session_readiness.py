"""Pure Task 9 Angel authentication/session readiness evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from services.contracts.task9_angel_auth_session_proof_v1 import (
    Task9AngelAuthProbeStatus,
    Task9AngelAuthSessionProofV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
    Task9AngelFailureDisposition,
    Task9AngelSessionCredentialKind,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupReasonCode,
    build_task9_startup_phase_result,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
)


class Task9AngelAuthReadinessStatus(
    str,
    Enum,
):
    READY = "READY"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    FAILED_FATAL = "FAILED_FATAL"


@dataclass(frozen=True, slots=True)
class Task9AngelAuthReadinessResultV1:
    status: Task9AngelAuthReadinessStatus

    proof_id: str

    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    reason_code: Task9StartupReasonCode | None

    incident_ref: str | None

    phase_result: Task9StartupPreflightPhaseResultV1

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelAuthReadinessStatus(
                    self.status
                ),
            )
            object.__setattr__(
                self,
                "live_proof_status",
                Task9LiveProofStatus(
                    self.live_proof_status
                ),
            )
            object.__setattr__(
                self,
                "readiness_status",
                Task9ProviderReadinessStatus(
                    self.readiness_status
                ),
            )
            if self.reason_code is not None:
                object.__setattr__(
                    self,
                    "reason_code",
                    Task9StartupReasonCode(
                        self.reason_code
                    ),
                )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Angel auth readiness result"
            ) from exc

        if (
            type(self.proof_id) is not str
            or not self.proof_id
        ):
            raise ValueError(
                "proof_id"
            )

        if (
            type(self.phase_result)
            is not Task9StartupPreflightPhaseResultV1
        ):
            raise TypeError(
                "phase_result"
            )

        if (
            self.phase_result.phase
            is not Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION
        ):
            raise ValueError(
                "wrong startup phase"
            )


def _pass_phase(
    observed_at: datetime,
) -> Task9StartupPreflightPhaseResultV1:
    return Task9StartupPreflightPhaseResultV1(
        Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION,
        Task9StartupPreflightPhaseStatus.PASS,
        False,
        "ANGEL_AUTH_SESSION_READY",
        None,
        observed_at,
    )


def evaluate_task9_angel_auth_session(
    *,
    authority: Task9AngelCapabilitySessionV1,
    proof: Task9AngelAuthSessionProofV1,
) -> Task9AngelAuthReadinessResultV1:
    if (
        type(authority)
        is not Task9AngelCapabilitySessionV1
    ):
        raise TypeError(
            "authority"
        )

    if (
        type(proof)
        is not Task9AngelAuthSessionProofV1
    ):
        raise TypeError(
            "proof"
        )

    auth_capability = authority.capability(
        Task9AngelCapability.AUTH_SESSION
    )

    if (
        auth_capability.readiness_status
        not in {
            Task9ProviderReadinessStatus.READY,
            Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF,
            Task9ProviderReadinessStatus.BLOCKED_RETRYABLE,
            Task9ProviderReadinessStatus.FAILED_FATAL,
        }
    ):
        raise ValueError(
            "TASK9_ANGEL_AUTH_CAPABILITY_STATE_INVALID"
        )

    if (
        proof.credential_references_present
        is not True
    ):
        reason = (
            Task9StartupReasonCode.MISSING_CREDENTIAL_REFERENCE
        )

        return Task9AngelAuthReadinessResultV1(
            status=(
                Task9AngelAuthReadinessStatus.FAILED_FATAL
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            reason_code=reason,
            incident_ref=proof.incident_ref,
            phase_result=(
                build_task9_startup_phase_result(
                    phase=(
                        Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION
                    ),
                    reason_code=reason,
                    observed_at=proof.observed_at,
                )
            ),
        )

    if (
        proof.status
        is Task9AngelAuthProbeStatus.READY
    ):
        expected = (
            Task9AngelSessionCredentialKind.JWT,
            Task9AngelSessionCredentialKind.REFRESH,
            Task9AngelSessionCredentialKind.FEED,
        )

        if (
            proof.credential_kinds_confirmed
            != expected
        ):
            raise ValueError(
                "TASK9_ANGEL_AUTH_READY_CREDENTIAL_PROOF_INVALID"
            )

        return Task9AngelAuthReadinessResultV1(
            status=(
                Task9AngelAuthReadinessStatus.READY
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PROVEN
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.READY
            ),
            reason_code=None,
            incident_ref=None,
            phase_result=(
                _pass_phase(
                    proof.observed_at
                )
            ),
        )

    if proof.provider_code is None:
        reason = (
            Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
        )

        return Task9AngelAuthReadinessResultV1(
            status=(
                Task9AngelAuthReadinessStatus.BLOCKED_RETRYABLE
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            reason_code=reason,
            incident_ref=proof.incident_ref,
            phase_result=(
                build_task9_startup_phase_result(
                    phase=(
                        Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION
                    ),
                    reason_code=reason,
                    observed_at=proof.observed_at,
                )
            ),
        )

    disposition = (
        authority.failure_codes.disposition_for(
            proof.provider_code
        )
    )

    try:
        reason = Task9StartupReasonCode(
            proof.provider_code
        )
    except ValueError:
        reason = (
            Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
        )

    if (
        disposition
        is Task9AngelFailureDisposition.FATAL
    ):
        return Task9AngelAuthReadinessResultV1(
            status=(
                Task9AngelAuthReadinessStatus.FAILED_FATAL
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            reason_code=reason,
            incident_ref=proof.incident_ref,
            phase_result=(
                build_task9_startup_phase_result(
                    phase=(
                        Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION
                    ),
                    reason_code=reason,
                    observed_at=proof.observed_at,
                )
            ),
        )

    if (
        disposition
        is Task9AngelFailureDisposition.RETRYABLE
    ):
        return Task9AngelAuthReadinessResultV1(
            status=(
                Task9AngelAuthReadinessStatus.BLOCKED_RETRYABLE
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            reason_code=reason,
            incident_ref=proof.incident_ref,
            phase_result=(
                build_task9_startup_phase_result(
                    phase=(
                        Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION
                    ),
                    reason_code=reason,
                    observed_at=proof.observed_at,
                )
            ),
        )

    return Task9AngelAuthReadinessResultV1(
        status=(
            Task9AngelAuthReadinessStatus.BLOCKED_RETRYABLE
        ),
        proof_id=proof.proof_id,
        live_proof_status=(
            Task9LiveProofStatus.PENDING
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
        ),
        reason_code=(
            Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
        ),
        incident_ref=proof.incident_ref,
        phase_result=(
            build_task9_startup_phase_result(
                phase=(
                    Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION
                ),
                reason_code=(
                    Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
                ),
                observed_at=proof.observed_at,
            )
        ),
    )
