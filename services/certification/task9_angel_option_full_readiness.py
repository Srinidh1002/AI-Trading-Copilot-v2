"""Pure Task 9 Angel NFO/BFO option FULL capability readiness."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_angel_option_full_proof_v1 import (
    Task9AngelOptionFullProbeStatus,
    Task9AngelOptionFullProofV1,
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


class Task9AngelOptionFullReadinessStatus(
    str,
    Enum,
):
    READY = "READY"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    FAILED_FATAL = "FAILED_FATAL"


@dataclass(frozen=True, slots=True)
class Task9AngelOptionFullReadinessV1:
    status: Task9AngelOptionFullReadinessStatus

    proof_id: str
    market: str
    exchange: str

    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    requested_contract_count: int
    fetched_contract_count: int
    unfetched_contract_count: int
    malformed_contract_count: int

    oldest_quote_age_seconds: float | None
    maximum_quote_age_seconds: float

    partial_response: bool

    reason_code: Task9StartupReasonCode | None
    incident_ref: str | None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelOptionFullReadinessStatus(
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
                "option FULL readiness"
            ) from exc

        if self.market not in {
            "NIFTY",
            "SENSEX",
        }:
            raise ValueError("market")

        if self.exchange not in {
            "NFO",
            "BFO",
        }:
            raise ValueError("exchange")

        if type(self.partial_response) is not bool:
            raise TypeError("partial_response")

        if (
            type(self.maximum_quote_age_seconds)
            not in (int, float)
            or isinstance(
                self.maximum_quote_age_seconds,
                bool,
            )
            or self.maximum_quote_age_seconds <= 0
        ):
            raise ValueError(
                "maximum_quote_age_seconds"
            )

        object.__setattr__(
            self,
            "maximum_quote_age_seconds",
            float(
                self.maximum_quote_age_seconds
            ),
        )

        if self.oldest_quote_age_seconds is not None:
            if (
                type(self.oldest_quote_age_seconds)
                not in (int, float)
                or isinstance(
                    self.oldest_quote_age_seconds,
                    bool,
                )
                or self.oldest_quote_age_seconds < 0
            ):
                raise ValueError(
                    "oldest_quote_age_seconds"
                )

            object.__setattr__(
                self,
                "oldest_quote_age_seconds",
                float(
                    self.oldest_quote_age_seconds
                ),
            )


def evaluate_task9_angel_option_full(
    *,
    authority: Task9AngelCapabilitySessionV1,
    runtime_config: Task9RuntimeConfigV1,
    proof: Task9AngelOptionFullProofV1,
) -> Task9AngelOptionFullReadinessV1:
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
        is not Task9AngelOptionFullProofV1
    ):
        raise TypeError("proof")

    capability = (
        Task9AngelCapability.NFO_OPTION_FULL
        if proof.market == "NIFTY"
        else Task9AngelCapability.BFO_OPTION_FULL
    )

    state = authority.capability(
        capability
    )

    if (
        state.market != proof.market
        or state.exchange != proof.exchange
    ):
        raise ValueError(
            "TASK9_ANGEL_OPTION_FULL_AUTHORITY_IDENTITY_MISMATCH"
        )

    maximum_age = float(
        runtime_config.option_quote_max_age_seconds
    )

    common = {
        "proof_id": proof.proof_id,
        "market": proof.market,
        "exchange": proof.exchange,
        "requested_contract_count": (
            proof.requested_contract_count
        ),
        "fetched_contract_count": (
            proof.fetched_contract_count
        ),
        "unfetched_contract_count": (
            proof.unfetched_contract_count
        ),
        "malformed_contract_count": (
            proof.malformed_contract_count
        ),
        "maximum_quote_age_seconds": maximum_age,
        "partial_response": (
            proof.status
            is Task9AngelOptionFullProbeStatus.PARTIAL
        ),
        "incident_ref": proof.incident_ref,
    }

    if proof.exchange_identity_verified is not True:
        return Task9AngelOptionFullReadinessV1(
            status=(
                Task9AngelOptionFullReadinessStatus.FAILED_FATAL
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            oldest_quote_age_seconds=None,
            reason_code=(
                Task9StartupReasonCode.WRONG_OPTION_EXCHANGE
            ),
            **common,
        )

    if (
        proof.status
        is Task9AngelOptionFullProbeStatus.UNAVAILABLE
    ):
        return Task9AngelOptionFullReadinessV1(
            status=(
                Task9AngelOptionFullReadinessStatus.BLOCKED_RETRYABLE
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            oldest_quote_age_seconds=None,
            reason_code=(
                Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
            ),
            **common,
        )

    if (
        proof.status
        is Task9AngelOptionFullProbeStatus.MALFORMED
    ):
        return Task9AngelOptionFullReadinessV1(
            status=(
                Task9AngelOptionFullReadinessStatus.BLOCKED_RETRYABLE
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            oldest_quote_age_seconds=None,
            reason_code=(
                Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
            ),
            **common,
        )

    if (
        proof.fetched_contract_count <= 0
        or proof.oldest_provider_timestamp is None
    ):
        raise ValueError(
            "TASK9_ANGEL_OPTION_FULL_FETCHED_EVIDENCE_MISSING"
        )

    oldest_age = (
        proof.observed_at
        - proof.oldest_provider_timestamp
    ).total_seconds()

    if oldest_age < 0:
        raise ValueError(
            "TASK9_ANGEL_OPTION_FULL_TIMESTAMP_FUTURE"
        )

    if oldest_age > maximum_age:
        return Task9AngelOptionFullReadinessV1(
            status=(
                Task9AngelOptionFullReadinessStatus.BLOCKED_RETRYABLE
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            oldest_quote_age_seconds=oldest_age,
            reason_code=(
                Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
            ),
            **common,
        )

    return Task9AngelOptionFullReadinessV1(
        status=(
            Task9AngelOptionFullReadinessStatus.READY
        ),
        live_proof_status=(
            Task9LiveProofStatus.PROVEN
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY
        ),
        oldest_quote_age_seconds=oldest_age,
        reason_code=None,
        **common,
    )
