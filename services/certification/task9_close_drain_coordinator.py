"""Canonical Task 9 close-drain coordinator."""
from __future__ import annotations

from datetime import date, datetime

from services.certification.task9_abstention_later_observation_recovery import (
    finalize_task9_expired_abstentions,
)
from services.certification.task9_close_drain_evaluator import (
    evaluate_task9_close_drain,
)
from services.certification.task9_close_drain_facts import (
    build_task9_close_drain_items,
)
from services.certification.task9_close_drain_state_store import (
    Task9CloseDrainStateStore,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainStateV1,
    Task9CloseDrainStatus,
)
from services.contracts.task9_market_session_state_v1 import (
    Task9SegmentSessionStateV1,
)


class Task9CloseDrainCoordinatorError(
    RuntimeError
):
    pass


def coordinate_task9_close_drain(
    *,
    official_run_id: str,
    market_date: date,
    evaluated_at: datetime,
    session_states: tuple[
        Task9SegmentSessionStateV1,
        Task9SegmentSessionStateV1,
    ],
    prediction_ledger,
    binding_store,
    lifecycle_context_store,
    observation_store,
    outcome_store,
    reconciliation_store,
    trade_persistence_service,
    outcome_policy: PredictionLifecycleOutcomePolicyV1,
    state_store: Task9CloseDrainStateStore,
    live_stream_root=None,
) -> Task9CloseDrainStateV1:
    """Drain only durable terminal work after canonical close."""

    if (
        type(outcome_policy)
        is not PredictionLifecycleOutcomePolicyV1
    ):
        raise TypeError("outcome_policy")

    if (
        type(state_store)
        is not Task9CloseDrainStateStore
    ):
        raise TypeError("state_store")

    def scan():
        return build_task9_close_drain_items(
            official_run_id=official_run_id,
            market_date=market_date,
            evaluated_at=evaluated_at,
            prediction_ledger=prediction_ledger,
            binding_store=binding_store,
            observation_store=observation_store,
            outcome_store=outcome_store,
            reconciliation_store=reconciliation_store,
            trade_persistence_service=(
                trade_persistence_service
            ),
        )

    before = evaluate_task9_close_drain(
        official_run_id=official_run_id,
        market_date=market_date,
        evaluated_at=evaluated_at,
        session_states=session_states,
        items=scan(),
    )

    # OPEN / PRE_OPEN / ENTRY_RESTRICTED /
    # NON_TRADING_DAY never run close recovery.
    if (
        before.status
        is Task9CloseDrainStatus.NOT_REQUIRED
    ):
        return state_store.save(before)

    try:
        finalize_task9_expired_abstentions(
            prediction_ledger=prediction_ledger,
            lifecycle_context_store=(
                lifecycle_context_store
            ),
            observation_store=observation_store,
            outcome_store=outcome_store,
            outcome_policy=outcome_policy,
            evaluated_at=evaluated_at,
            live_stream_root=live_stream_root,
        )
    except Exception as exc:
        # Persist a fail-visible projection when durable
        # facts permit one, but never convert failure to
        # COMPLETE.
        after_failure = (
            evaluate_task9_close_drain(
                official_run_id=official_run_id,
                market_date=market_date,
                evaluated_at=evaluated_at,
                session_states=session_states,
                items=scan(),
            )
        )

        if (
            after_failure.status
            is Task9CloseDrainStatus.COMPLETE
        ):
            raise Task9CloseDrainCoordinatorError(
                "close-drain recovery failed "
                "before completion could be trusted"
            ) from exc

        state_store.save(
            after_failure
        )

        raise Task9CloseDrainCoordinatorError(
            "TASK9_CLOSE_DRAIN_RECOVERY_FAILED"
        ) from exc

    final_state = evaluate_task9_close_drain(
        official_run_id=official_run_id,
        market_date=market_date,
        evaluated_at=evaluated_at,
        session_states=session_states,
        items=scan(),
    )

    return state_store.save(
        final_state
    )
