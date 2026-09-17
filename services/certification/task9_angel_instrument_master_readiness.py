"""Pure Task 9 Angel instrument-master freshness/readiness evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_angel_instrument_master_proof_v1 import (
    Task9AngelInstrumentMasterProbeStatus,
    Task9AngelInstrumentMasterProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupReasonCode,
)


class Task9AngelInstrumentMasterReadinessStatus(
    str,
    Enum,
):
    READY = "READY"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    FAILED_FATAL = "FAILED_FATAL"


@dataclass(frozen=True, slots=True)
class Task9AngelInstrumentMasterReadinessV1:
    status: Task9AngelInstrumentMasterReadinessStatus

    proof_id: str

    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    age_seconds: float | None
    maximum_age_seconds: float

    reason_code: Task9StartupReasonCode | None
    incident_ref: str | None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelInstrumentMasterReadinessStatus(
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
                "instrument master readiness"
            ) from exc

        if (
            type(self.proof_id) is not str
            or not self.proof_id
        ):
            raise ValueError(
                "proof_id"
            )

        if (
            type(self.maximum_age_seconds)
            not in (int, float)
            or isinstance(
                self.maximum_age_seconds,
                bool,
            )
            or self.maximum_age_seconds <= 0
        ):
            raise ValueError(
                "maximum_age_seconds"
            )

        object.__setattr__(
            self,
            "maximum_age_seconds",
            float(
                self.maximum_age_seconds
            ),
        )

        if self.age_seconds is not None:
            if (
                type(self.age_seconds)
                not in (int, float)
                or isinstance(
                    self.age_seconds,
                    bool,
                )
                or self.age_seconds < 0
            ):
                raise ValueError(
                    "age_seconds"
                )

            object.__setattr__(
                self,
                "age_seconds",
                float(
                    self.age_seconds
                ),
            )


def evaluate_task9_angel_instrument_master(
    *,
    authority: Task9AngelCapabilitySessionV1,
    runtime_config: Task9RuntimeConfigV1,
    proof: Task9AngelInstrumentMasterProofV1,
) -> Task9AngelInstrumentMasterReadinessV1:
    if (
        type(authority)
        is not Task9AngelCapabilitySessionV1
    ):
        raise TypeError("authority")

    if (
        type(runtime_config)
        is not Task9RuntimeConfigV1
    ):
        raise TypeError("runtime_config")

    if (
        type(proof)
        is not Task9AngelInstrumentMasterProofV1
    ):
        raise TypeError("proof")

    capability = authority.capability(
        Task9AngelCapability.INSTRUMENT_MASTER
    )

    if (
        capability.readiness_status
        not in {
            Task9ProviderReadinessStatus.READY,
            Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF,
            Task9ProviderReadinessStatus.BLOCKED_RETRYABLE,
            Task9ProviderReadinessStatus.FAILED_FATAL,
        }
    ):
        raise ValueError(
            "TASK9_ANGEL_INSTRUMENT_MASTER_CAPABILITY_INVALID"
        )

    maximum_age = float(
        runtime_config.instrument_master_max_age_seconds
    )

    if (
        proof.status
        is Task9AngelInstrumentMasterProbeStatus.CORRUPT
    ):
        return Task9AngelInstrumentMasterReadinessV1(
            status=(
                Task9AngelInstrumentMasterReadinessStatus.FAILED_FATAL
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            age_seconds=None,
            maximum_age_seconds=maximum_age,
            reason_code=(
                Task9StartupReasonCode.INSTRUMENT_MASTER_CORRUPT
            ),
            incident_ref=proof.incident_ref,
        )

    if (
        proof.status
        is Task9AngelInstrumentMasterProbeStatus.UNAVAILABLE
    ):
        return Task9AngelInstrumentMasterReadinessV1(
            status=(
                Task9AngelInstrumentMasterReadinessStatus.BLOCKED_RETRYABLE
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            age_seconds=None,
            maximum_age_seconds=maximum_age,
            reason_code=(
                Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
            ),
            incident_ref=proof.incident_ref,
        )

    if proof.fetched_at is None:
        raise ValueError(
            "TASK9_INSTRUMENT_MASTER_FETCH_TIME_MISSING"
        )

    age_seconds = (
        proof.observed_at
        - proof.fetched_at
    ).total_seconds()

    if age_seconds < 0:
        raise ValueError(
            "TASK9_INSTRUMENT_MASTER_FUTURE_TIMESTAMP"
        )

    if age_seconds > maximum_age:
        return Task9AngelInstrumentMasterReadinessV1(
            status=(
                Task9AngelInstrumentMasterReadinessStatus.BLOCKED_RETRYABLE
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            age_seconds=age_seconds,
            maximum_age_seconds=maximum_age,
            reason_code=(
                Task9StartupReasonCode.INSTRUMENT_MASTER_STALE
            ),
            incident_ref=proof.incident_ref,
        )

    if (
        proof.nifty_nfo_identity_present
        is not True
        or proof.sensex_bfo_identity_present
        is not True
    ):
        return Task9AngelInstrumentMasterReadinessV1(
            status=(
                Task9AngelInstrumentMasterReadinessStatus.FAILED_FATAL
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            age_seconds=age_seconds,
            maximum_age_seconds=maximum_age,
            reason_code=(
                Task9StartupReasonCode.INSTRUMENT_MASTER_CORRUPT
            ),
            incident_ref=proof.incident_ref,
        )

    if (
        proof.record_count is None
        or proof.record_count <= 0
    ):
        raise ValueError(
            "TASK9_INSTRUMENT_MASTER_RECORD_COUNT_INVALID"
        )

    return Task9AngelInstrumentMasterReadinessV1(
        status=(
            Task9AngelInstrumentMasterReadinessStatus.READY
        ),
        proof_id=proof.proof_id,
        live_proof_status=(
            Task9LiveProofStatus.PROVEN
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY
        ),
        age_seconds=age_seconds,
        maximum_age_seconds=maximum_age,
        reason_code=None,
        incident_ref=None,
    )
