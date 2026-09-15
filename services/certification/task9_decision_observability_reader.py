"""Read-only Task 9 decision observability adapter.

This module never persists decision state and never calls providers.
It projects already-persisted Task 9 live decision audits into the
Lane-B observability contract.
"""

from __future__ import annotations

from collections.abc import Callable

from services.certification.task9_decision_observability_projector import (
    build_task9_decision_observability,
)
from services.certification.task9_live_decision_audit import (
    Task9LiveDecisionAuditStore,
)
from services.contracts.canonical_directional_policy_v1 import (
    CanonicalDirectionalPolicyV1,
)
from services.contracts.task9_decision_observability_v1 import (
    Task9DecisionObservabilityV1,
    Task9ProviderParticipationV1,
)
from services.contracts.task9_live_decision_audit_v1 import (
    Task9LiveDecisionAuditV1,
)


PolicyReader = Callable[
    [Task9LiveDecisionAuditV1],
    CanonicalDirectionalPolicyV1 | None,
]

CapitalReader = Callable[
    [Task9LiveDecisionAuditV1],
    object | None,
]

ProviderReader = Callable[
    [Task9LiveDecisionAuditV1],
    tuple[Task9ProviderParticipationV1, ...],
]


def _none_policy(
    audit: Task9LiveDecisionAuditV1,
) -> CanonicalDirectionalPolicyV1 | None:
    return None


def _none_capital(
    audit: Task9LiveDecisionAuditV1,
) -> object | None:
    return None


def _no_providers(
    audit: Task9LiveDecisionAuditV1,
) -> tuple[Task9ProviderParticipationV1, ...]:
    return ()


def read_task9_decision_observability(
    *,
    audit_store: Task9LiveDecisionAuditStore,
    prediction_id: str,
    policy_reader: PolicyReader = _none_policy,
    capital_reader: CapitalReader = _none_capital,
    provider_reader: ProviderReader = _no_providers,
    required_confidence: float | None = None,
    required_directional_families: int | None = None,
) -> Task9DecisionObservabilityV1 | None:
    if type(audit_store) is not Task9LiveDecisionAuditStore:
        raise TypeError("audit_store")

    if type(prediction_id) is not str or not prediction_id.strip():
        raise ValueError("prediction_id")

    if not callable(policy_reader):
        raise TypeError("policy_reader")

    if not callable(capital_reader):
        raise TypeError("capital_reader")

    if not callable(provider_reader):
        raise TypeError("provider_reader")

    audit = audit_store.recover(
        prediction_id.strip()
    )

    if audit is None:
        return None

    policy = policy_reader(audit)

    if (
        policy is not None
        and type(policy)
        is not CanonicalDirectionalPolicyV1
    ):
        raise TypeError("policy_reader result")

    capital = capital_reader(audit)

    providers = provider_reader(audit)

    if not isinstance(providers, tuple):
        raise TypeError("provider_reader result")

    if any(
        type(item)
        is not Task9ProviderParticipationV1
        for item in providers
    ):
        raise TypeError(
            "provider_reader result item"
        )

    if policy is None:
        effective_required_confidence = None
        effective_required_families = None
    else:
        if (
            required_confidence is None
            or required_directional_families is None
        ):
            raise ValueError(
                "policy thresholds required"
            )

        effective_required_confidence = (
            required_confidence
        )

        effective_required_families = (
            required_directional_families
        )

    return build_task9_decision_observability(
        audit=audit,
        canonical_policy=policy,
        required_confidence=(
            effective_required_confidence
        ),
        required_directional_families=(
            effective_required_families
        ),
        capital_result=capital,
        provider_participation=providers,
    )


__all__ = (
    "read_task9_decision_observability",
)
