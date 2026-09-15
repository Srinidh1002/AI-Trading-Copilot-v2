"""Pure Task 9 Angel request-budget/readiness evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_angel_request_budget_proof_v1 import (
    Task9AngelRequestBudgetProbeStatus,
    Task9AngelRequestBudgetProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
)


class Task9AngelRequestBudgetReadinessStatus(
    str,
    Enum,
):
    READY = "READY"
    BLOCKED_RETRYABLE = "BLOCKED_RETRYABLE"
    FAILED_FATAL = "FAILED_FATAL"


@dataclass(frozen=True, slots=True)
class Task9AngelRequestBudgetReadinessV1:
    status: Task9AngelRequestBudgetReadinessStatus

    proof_id: str
    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    controller_thread_safe: bool
    account_wide_budget_owner: bool
    endpoint_scoped_cooldowns: bool

    historical_isolated_from_market_data: bool
    historical_isolated_from_greeks: bool

    launcher_request_burst_owner: bool

    incident_ref: str | None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelRequestBudgetReadinessStatus(
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
                "request-budget readiness"
            ) from exc


def evaluate_task9_angel_request_budget(
    *,
    authority: Task9AngelCapabilitySessionV1,
    proof: Task9AngelRequestBudgetProofV1,
) -> Task9AngelRequestBudgetReadinessV1:
    if (
        type(authority)
        is not Task9AngelCapabilitySessionV1
    ):
        raise TypeError("authority")

    if (
        type(proof)
        is not Task9AngelRequestBudgetProofV1
    ):
        raise TypeError("proof")

    state = authority.capability(
        Task9AngelCapability.REQUEST_BUDGET
    )

    requirement_value = getattr(
        state.requirement,
        "value",
        state.requirement,
    )

    if requirement_value != "REQUIRED":
        raise ValueError(
            "TASK9_REQUEST_BUDGET_MUST_BE_REQUIRED"
        )

    structural_failure = (
        proof.controller_thread_safe is not True
        or proof.account_wide_budget_owner is not True
        or proof.endpoint_scoped_cooldowns is not True
        or proof.historical_isolated_from_market_data is not True
        or proof.historical_isolated_from_greeks is not True
        or proof.angel_client_transport_retry_owner is not True
        or proof.launcher_next_cycle_retry_only is not True
        or proof.cache_owned_by_controller is not True
        or proof.launcher_request_burst_owner is True
    )

    common = {
        "proof_id": proof.proof_id,
        "controller_thread_safe": (
            proof.controller_thread_safe
        ),
        "account_wide_budget_owner": (
            proof.account_wide_budget_owner
        ),
        "endpoint_scoped_cooldowns": (
            proof.endpoint_scoped_cooldowns
        ),
        "historical_isolated_from_market_data": (
            proof.historical_isolated_from_market_data
        ),
        "historical_isolated_from_greeks": (
            proof.historical_isolated_from_greeks
        ),
        "launcher_request_burst_owner": (
            proof.launcher_request_burst_owner
        ),
        "incident_ref": proof.incident_ref,
    }

    if (
        proof.status
        is Task9AngelRequestBudgetProbeStatus.INVALID
        or structural_failure
    ):
        return Task9AngelRequestBudgetReadinessV1(
            status=(
                Task9AngelRequestBudgetReadinessStatus.FAILED_FATAL
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.FAILED_FATAL
            ),
            **common,
        )

    if (
        proof.status
        is Task9AngelRequestBudgetProbeStatus.BLOCKED_RETRYABLE
    ):
        return Task9AngelRequestBudgetReadinessV1(
            status=(
                Task9AngelRequestBudgetReadinessStatus.BLOCKED_RETRYABLE
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
            ),
            **common,
        )

    return Task9AngelRequestBudgetReadinessV1(
        status=(
            Task9AngelRequestBudgetReadinessStatus.READY
        ),
        live_proof_status=(
            Task9LiveProofStatus.PROVEN
        ),
        readiness_status=(
            Task9ProviderReadinessStatus.READY
        ),
        **common,
    )
