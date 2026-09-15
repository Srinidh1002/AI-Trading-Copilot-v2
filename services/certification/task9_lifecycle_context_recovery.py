"""Deterministic recovery for a Task 9 prediction/context partial commit."""
from __future__ import annotations

from dataclasses import dataclass

from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.contracts.prediction_lifecycle_timing_v1 import (
    PredictionLifecycleWindowV1,
)
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.market_session.policies import MarketSessionPolicy


_ABSTENTION_IDENTITIES = frozenset({("NIFTY", "NSE"), ("SENSEX", "BSE")})
_ABSTENTION_ACTIONS = frozenset({"WAIT", "NO_TRADE"})


@dataclass(frozen=True, slots=True)
class Task9LifecycleContextRecoveryV1:
    context: PredictionLifecycleWindowV1
    persistence_status: str


def recover_or_reconstruct_task9_lifecycle_context(
    *,
    prediction: PredictionRecordV1,
    lifecycle_context_store: Task9PredictionLifecycleContextStore,
    session_policy: MarketSessionPolicy,
) -> Task9LifecycleContextRecoveryV1:
    """Recover an authoritative context or recreate only the missing one.

    The canonical timing resolver is the sole timestamp/provenance authority.
    An existing payload must exactly equal that resolver result; it is never
    replaced on recovery.
    """
    if type(prediction) is not PredictionRecordV1:
        raise TypeError("prediction")
    if type(lifecycle_context_store) is not Task9PredictionLifecycleContextStore:
        raise TypeError("lifecycle_context_store")
    if type(session_policy) is not MarketSessionPolicy:
        raise TypeError("session_policy")
    if (
        prediction.terminal_status != "COMPLETED"
        or prediction.predicted_action not in _ABSTENTION_ACTIONS
        or (prediction.underlying_symbol, prediction.exchange)
        not in _ABSTENTION_IDENTITIES
    ):
        raise ValueError("Task9 abstention lifecycle reconstruction identity")

    expected = resolve_prediction_lifecycle_window(
        prediction_record=prediction,
        session_policy=session_policy,
    )
    existing = lifecycle_context_store.recover(prediction.prediction_id)
    if existing is not None:
        if existing != expected:
            raise ValueError("conflicting lifecycle context reconstruction")
        return Task9LifecycleContextRecoveryV1(existing, "EXISTING")

    persistence_status = lifecycle_context_store.save(expected)
    recovered = lifecycle_context_store.recover(prediction.prediction_id)
    if recovered != expected:
        raise ValueError("lifecycle context reconstruction persistence")
    return Task9LifecycleContextRecoveryV1(recovered, persistence_status)


__all__ = (
    "Task9LifecycleContextRecoveryV1",
    "recover_or_reconstruct_task9_lifecycle_context",
)
