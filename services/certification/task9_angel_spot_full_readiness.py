"""Pure per-market Task 9 Angel spot FULL readiness evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_angel_spot_full_proof_v1 import (
    Task9AngelSpotFullProbeStatus,
    Task9AngelSpotFullProofV1,
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


class Task9AngelSpotFullReadinessStatus(
    str,
    Enum,
):
    READY = "READY"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    FAILED_FATAL = "FAILED_FATAL"


@dataclass(frozen=True, slots=True)
class Task9AngelSpotFullReadinessV1:
    status: Task9AngelSpotFullReadinessStatus

    proof_id: str
    market: str
    exchange: str
    token: str

    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    quote_age_seconds: float | None
    maximum_quote_age_seconds: float

    reason_code: Task9StartupReasonCode | None
    incident_ref: str | None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelSpotFullReadinessStatus(
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
                "spot FULL readiness"
            ) from exc

        if self.market not in {
            "NIFTY",
            "SENSEX",
        }:
            raise ValueError("market")

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

        if self.quote_age_seconds is not None:
            if (
                type(self.quote_age_seconds)
                not in (int, float)
                or isinstance(
                    self.quote_age_seconds,
                    bool,
                )
                or self.quote_age_seconds < 0
            ):
                raise ValueError(
                    "quote_age_seconds"
                )

            object.__setattr__(
                self,
                "quote_age_seconds",
                float(
                    self.quote_age_seconds
                ),
            )


def evaluate_task9_angel_spot_full(
    *,
    authority: Task9AngelCapabilitySessionV1,
    runtime_config: Task9RuntimeConfigV1,
    proof: Task9AngelSpotFullProofV1,
) -> Task9AngelSpotFullReadinessV1:
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
        is not Task9AngelSpotFullProofV1
    ):
        raise TypeError("proof")

    capability = (
        Task9AngelCapability.NIFTY_SPOT_FULL
        if proof.market == "NIFTY"
        else Task9AngelCapability.SENSEX_SPOT_FULL
    )

    state = authority.capability(
        capability
    )

    if (
        state.market != proof.market
        or state.exchange != proof.exchange
    ):
        raise ValueError(
            "TASK9_ANGEL_SPOT_AUTHORITY_IDENTITY_MISMATCH"
        )

    maximum_age = float(
        runtime_config.market_quote_max_age_seconds
    )

    if (
        proof.status
        is Task9AngelSpotFullProbeStatus.UNAVAILABLE
    ):
        return Task9AngelSpotFullReadinessV1(
            status=(
                Task9AngelSpotFullReadinessStatus.BLOCKED_RETRYABLE
            ),
            proof_id=proof.proof_id,
            market=proof.market,
            exchange=proof.exchange,
            token=proof.token,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            quote_age_seconds=None,
            maximum_quote_age_seconds=maximum_age,
            reason_code=(
                Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
            ),
            incident_ref=proof.incident_ref,
        )

    if (
        proof.status
        is Task9AngelSpotFullProbeStatus.MALFORMED
    ):
        reason = (
            Task9StartupReasonCode.WRONG_NIFTY_IDENTITY
            if proof.market == "NIFTY"
            else Task9StartupReasonCode.WRONG_SENSEX_IDENTITY
        )

        return Task9AngelSpotFullReadinessV1(
            status=(
                Task9AngelSpotFullReadinessStatus.FAILED_FATAL
            ),
            proof_id=proof.proof_id,
            market=proof.market,
            exchange=proof.exchange,
            token=proof.token,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            quote_age_seconds=None,
            maximum_quote_age_seconds=maximum_age,
            reason_code=reason,
            incident_ref=proof.incident_ref,
        )

    if proof.identity_verified is not True:
        reason = (
            Task9StartupReasonCode.WRONG_NIFTY_IDENTITY
            if proof.market == "NIFTY"
            else Task9StartupReasonCode.WRONG_SENSEX_IDENTITY
        )

        return Task9AngelSpotFullReadinessV1(
            status=(
                Task9AngelSpotFullReadinessStatus.FAILED_FATAL
            ),
            proof_id=proof.proof_id,
            market=proof.market,
            exchange=proof.exchange,
            token=proof.token,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            quote_age_seconds=None,
            maximum_quote_age_seconds=maximum_age,
            reason_code=reason,
            incident_ref=proof.incident_ref,
        )

    if proof.provider_timestamp is None:
        raise ValueError(
            "TASK9_ANGEL_SPOT_PROVIDER_TIMESTAMP_MISSING"
        )

    age = (
        proof.observed_at
        - proof.provider_timestamp
    ).total_seconds()

    if age < 0:
        raise ValueError(
            "TASK9_ANGEL_SPOT_PROVIDER_TIMESTAMP_FUTURE"
        )

    if age > maximum_age:
        return Task9AngelSpotFullReadinessV1(
            status=(
                Task9AngelSpotFullReadinessStatus.BLOCKED_RETRYABLE
            ),
            proof_id=proof.proof_id,
            market=proof.market,
            exchange=proof.exchange,
            token=proof.token,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            quote_age_seconds=age,
            maximum_quote_age_seconds=maximum_age,
            reason_code=(
                Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
            ),
            incident_ref=proof.incident_ref,
        )

    return Task9AngelSpotFullReadinessV1(
        status=(
            Task9AngelSpotFullReadinessStatus.READY
        ),
        proof_id=proof.proof_id,
        market=proof.market,
        exchange=proof.exchange,
        token=proof.token,
        live_proof_status=(
            Task9LiveProofStatus.PROVEN
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY
        ),
        quote_age_seconds=age,
        maximum_quote_age_seconds=maximum_age,
        reason_code=None,
        incident_ref=None,
    )
