"""Pure optional Task 9 Angel India VIX readiness evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_angel_india_vix_proof_v1 import (
    Task9AngelIndiaVixProbeStatus,
    Task9AngelIndiaVixProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)


class Task9AngelIndiaVixReadinessStatus(
    str,
    Enum,
):
    READY = "READY"
    UNAVAILABLE_OPTIONAL = "UNAVAILABLE_OPTIONAL"


@dataclass(frozen=True, slots=True)
class Task9AngelIndiaVixReadinessV1:
    status: Task9AngelIndiaVixReadinessStatus

    proof_id: str

    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    quote_age_seconds: float | None
    maximum_quote_age_seconds: float

    identity_verified: bool
    incident_ref: str | None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelIndiaVixReadinessStatus(
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
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "India VIX readiness"
            ) from exc

        if type(
            self.identity_verified
        ) is not bool:
            raise TypeError(
                "identity_verified"
            )

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


def evaluate_task9_angel_india_vix(
    *,
    authority: Task9AngelCapabilitySessionV1,
    runtime_config: Task9RuntimeConfigV1,
    proof: Task9AngelIndiaVixProofV1,
) -> Task9AngelIndiaVixReadinessV1:
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
        is not Task9AngelIndiaVixProofV1
    ):
        raise TypeError("proof")

    state = authority.capability(
        Task9AngelCapability.INDIA_VIX
    )

    if (
        state.market != "INDIA_VIX"
        or state.exchange != "NSE"
    ):
        raise ValueError(
            "TASK9_ANGEL_INDIA_VIX_AUTHORITY_IDENTITY_MISMATCH"
        )

    maximum_age = float(
        runtime_config.market_quote_max_age_seconds
    )

    if (
        proof.status
        is not Task9AngelIndiaVixProbeStatus.AVAILABLE
        or proof.identity_verified is not True
    ):
        return Task9AngelIndiaVixReadinessV1(
            status=(
                Task9AngelIndiaVixReadinessStatus.UNAVAILABLE_OPTIONAL
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
            ),
            quote_age_seconds=None,
            maximum_quote_age_seconds=maximum_age,
            identity_verified=(
                proof.identity_verified
            ),
            incident_ref=proof.incident_ref,
        )

    if proof.provider_timestamp is None:
        raise ValueError(
            "TASK9_INDIA_VIX_TIMESTAMP_MISSING"
        )

    age = (
        proof.observed_at
        - proof.provider_timestamp
    ).total_seconds()

    if age < 0:
        raise ValueError(
            "TASK9_INDIA_VIX_TIMESTAMP_FUTURE"
        )

    if age > maximum_age:
        return Task9AngelIndiaVixReadinessV1(
            status=(
                Task9AngelIndiaVixReadinessStatus.UNAVAILABLE_OPTIONAL
            ),
            proof_id=proof.proof_id,
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
            ),
            quote_age_seconds=age,
            maximum_quote_age_seconds=maximum_age,
            identity_verified=True,
            incident_ref=proof.incident_ref,
        )

    return Task9AngelIndiaVixReadinessV1(
        status=(
            Task9AngelIndiaVixReadinessStatus.READY
        ),
        proof_id=proof.proof_id,
        live_proof_status=(
            Task9LiveProofStatus.PROVEN
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY
        ),
        quote_age_seconds=age,
        maximum_quote_age_seconds=maximum_age,
        identity_verified=True,
        incident_ref=None,
    )
