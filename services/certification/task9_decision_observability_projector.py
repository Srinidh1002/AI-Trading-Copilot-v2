"""Pure read-only Task 9 decision observability projector."""

from __future__ import annotations

from collections.abc import Mapping

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


def _mapping(
    value: object,
) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _texts_from(
    value: object,
) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        return ()

    return tuple(
        item.strip()
        for item in value
        if type(item) is str
        and item.strip()
    )


def _candidate_reached(
    audit: Task9LiveDecisionAuditV1,
) -> bool:
    if not audit.evaluation_present:
        return False

    snapshot = _mapping(
        audit.evaluation_snapshot
    )

    if snapshot is None:
        return False

    candidate = snapshot.get(
        "candidate"
    )

    if candidate is not None:
        return True

    return bool(
        audit.prediction_direction is not None
        or audit.prediction_eligibility is not None
    )


def _ranking_reached(
    audit: Task9LiveDecisionAuditV1,
) -> bool:
    if audit.trade_planner_reached:
        return True

    snapshot = _mapping(
        audit.evaluation_snapshot
    )

    if snapshot is None:
        return False

    for key in (
        "option_contract_eligibility",
        "option_ranking",
        "ranking",
        "selected_option_contract",
    ):
        if snapshot.get(key) is not None:
            return True

    return False


def _decision_reasons(
    audit: Task9LiveDecisionAuditV1,
) -> tuple[str, ...]:
    snapshot = _mapping(
        audit.evaluation_snapshot
    )

    if snapshot is None:
        return ()

    results: list[str] = []

    for key in (
        "reasons",
        "decision_reasons",
    ):
        for item in _texts_from(
            snapshot.get(key)
        ):
            if item not in results:
                results.append(item)

    for nested_key in (
        "pre_entry_action",
        "candidate",
        "canonical_directional_policy",
    ):
        nested = _mapping(
            snapshot.get(nested_key)
        )

        if nested is None:
            continue

        for key in (
            "reasons",
            "decision_reasons",
        ):
            for item in _texts_from(
                nested.get(key)
            ):
                if item not in results:
                    results.append(item)

    return tuple(results)


def _capital_value(
    capital_result: object,
    name: str,
) -> object:
    if capital_result is None:
        return None

    return getattr(
        capital_result,
        name,
        None,
    )


def build_task9_decision_observability(
    *,
    audit: Task9LiveDecisionAuditV1,
    canonical_policy: (
        CanonicalDirectionalPolicyV1 | None
    ) = None,
    required_confidence: float | None = None,
    required_directional_families: int | None = None,
    capital_result: object | None = None,
    provider_participation: tuple[
        Task9ProviderParticipationV1,
        ...
    ] = (),
) -> Task9DecisionObservabilityV1:
    if type(audit) is not Task9LiveDecisionAuditV1:
        raise TypeError("audit")

    if (
        canonical_policy is not None
        and type(canonical_policy)
        is not CanonicalDirectionalPolicyV1
    ):
        raise TypeError("canonical_policy")

    if (
        required_confidence is None
    ) != (
        canonical_policy is None
    ):
        raise ValueError(
            "required_confidence must accompany policy"
        )

    if (
        required_directional_families is None
    ) != (
        canonical_policy is None
    ):
        raise ValueError(
            "required_directional_families must accompany policy"
        )

    actual_confidence = (
        None
        if canonical_policy is None
        else canonical_policy.confidence
    )

    supporting_families = (
        ()
        if canonical_policy is None
        else canonical_policy.supporting_families
    )

    opposing_families = (
        ()
        if canonical_policy is None
        else canonical_policy.opposing_families
    )

    supporting_family_count = (
        None
        if canonical_policy is None
        else len(supporting_families)
    )

    confidence_margin = (
        None
        if actual_confidence is None
        else (
            float(actual_confidence)
            - float(required_confidence)
        )
    )

    family_margin = (
        None
        if supporting_family_count is None
        else (
            supporting_family_count
            - int(required_directional_families)
        )
    )

    capital_reached = capital_result is not None

    return Task9DecisionObservabilityV1(
        audit_id=audit.audit_id,
        parent_cycle_id=audit.parent_cycle_id,
        prediction_id=audit.prediction_id,
        market=audit.underlying_symbol,
        exchange=audit.exchange,
        action=audit.prediction_action,
        direction=audit.prediction_direction,
        eligibility=audit.prediction_eligibility,
        first_causal_blocker=(
            audit.first_causal_blocker
        ),
        concurrent_blockers=(
            audit.prediction_blockers
        ),
        decision_reasons=(
            _decision_reasons(audit)
        ),
        actual_confidence=actual_confidence,
        required_confidence=required_confidence,
        confidence_margin=confidence_margin,
        supporting_family_count=(
            supporting_family_count
        ),
        required_family_count=(
            required_directional_families
        ),
        family_margin=family_margin,
        supporting_families=(
            supporting_families
        ),
        opposing_families=(
            opposing_families
        ),
        candidate_reached=(
            _candidate_reached(audit)
        ),
        ranking_reached=(
            _ranking_reached(audit)
        ),
        planning_reached=(
            audit.trade_planner_reached
        ),
        capital_authority_reached=(
            capital_reached
        ),
        paper_entry_reached=(
            audit.entry_observation_present
        ),
        capital_status=(
            _capital_value(
                capital_result,
                "status",
            )
        ),
        available_capital=(
            _capital_value(
                capital_result,
                "available_capital",
            )
        ),
        estimated_one_lot_premium_cost=(
            _capital_value(
                capital_result,
                "estimated_one_lot_premium_cost",
            )
        ),
        estimated_total_capital_requirement=(
            _capital_value(
                capital_result,
                "estimated_total_capital_requirement",
            )
        ),
        planned_lot_count=(
            _capital_value(
                capital_result,
                "planned_lot_count",
            )
        ),
        planned_quantity=(
            _capital_value(
                capital_result,
                "planned_quantity",
            )
        ),
        capital_blockers=(
            ()
            if capital_result is None
            else tuple(
                getattr(
                    capital_result,
                    "blockers",
                    (),
                )
            )
        ),
        capital_reasons=(
            ()
            if capital_result is None
            else tuple(
                getattr(
                    capital_result,
                    "decision_reasons",
                    (),
                )
            )
        ),
        provider_participation=(
            provider_participation
        ),
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "build_task9_decision_observability",
)
