"""Pure Task 9 Angel NFO/BFO Greeks capability evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_angel_greeks_proof_v1 import (
    Task9AngelGreeksProbeStatus,
    Task9AngelGreeksProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
)


class Task9AngelGreeksReadinessStatus(
    str,
    Enum,
):
    READY = "READY"
    UNAVAILABLE_OPTIONAL = "UNAVAILABLE_OPTIONAL"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class Task9AngelGreeksReadinessV1:
    status: Task9AngelGreeksReadinessStatus

    proof_id: str
    market: str
    exchange: str

    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    requested_contract_count: int
    enriched_contract_count: int
    unavailable_contract_count: int

    partial_response: bool
    incident_ref: str | None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelGreeksReadinessStatus(
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
                "Greeks readiness"
            ) from exc

        if (self.market, self.exchange) not in {
            ("NIFTY", "NFO"),
            ("SENSEX", "BFO"),
        }:
            raise ValueError(
                "Greeks readiness identity"
            )

        if type(
            self.partial_response
        ) is not bool:
            raise TypeError(
                "partial_response"
            )


def evaluate_task9_angel_greeks(
    *,
    authority: Task9AngelCapabilitySessionV1,
    proof: Task9AngelGreeksProofV1,
) -> Task9AngelGreeksReadinessV1:
    if (
        type(authority)
        is not Task9AngelCapabilitySessionV1
    ):
        raise TypeError("authority")

    if (
        type(proof)
        is not Task9AngelGreeksProofV1
    ):
        raise TypeError("proof")

    capability = (
        Task9AngelCapability.NFO_OPTION_GREEKS
        if proof.market == "NIFTY"
        else Task9AngelCapability.BFO_OPTION_GREEKS
    )

    state = authority.capability(
        capability
    )

    if (
        state.market != proof.market
        or state.exchange != proof.exchange
    ):
        raise ValueError(
            "TASK9_ANGEL_GREEKS_AUTHORITY_IDENTITY_MISMATCH"
        )

    common = {
        "proof_id": proof.proof_id,
        "market": proof.market,
        "exchange": proof.exchange,
        "requested_contract_count": (
            proof.requested_contract_count
        ),
        "enriched_contract_count": (
            proof.enriched_contract_count
        ),
        "unavailable_contract_count": (
            proof.unavailable_contract_count
        ),
        "partial_response": (
            proof.status
            is Task9AngelGreeksProbeStatus.PARTIAL
        ),
        "incident_ref": proof.incident_ref,
    }

    if proof.market == "SENSEX":
        if (
            proof.status
            is not Task9AngelGreeksProbeStatus.UNSUPPORTED
        ):
            raise ValueError(
                "TASK9_BFO_GREEKS_MUST_REMAIN_UNSUPPORTED"
            )

        return Task9AngelGreeksReadinessV1(
            status=(
                Task9AngelGreeksReadinessStatus.UNSUPPORTED
            ),
            live_proof_status=(
                Task9LiveProofStatus.NOT_APPLICABLE
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.UNSUPPORTED
            ),
            **common,
        )

    if (
        proof.status
        in {
            Task9AngelGreeksProbeStatus.AVAILABLE,
            Task9AngelGreeksProbeStatus.PARTIAL,
        }
        and proof.enriched_contract_count > 0
    ):
        return Task9AngelGreeksReadinessV1(
            status=(
                Task9AngelGreeksReadinessStatus.READY
            ),
            live_proof_status=(
                Task9LiveProofStatus.PROVEN
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.READY
            ),
            **common,
        )

    return Task9AngelGreeksReadinessV1(
        status=(
            Task9AngelGreeksReadinessStatus.UNAVAILABLE_OPTIONAL
        ),
        live_proof_status=(
            Task9LiveProofStatus.PENDING
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL
        ),
        **common,
    )
