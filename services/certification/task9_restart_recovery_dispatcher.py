"""Deterministic Task 9 restart classification over durable prediction facts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from services.certification.task9_lifecycle_context_recovery import (
    recover_or_reconstruct_task9_lifecycle_context,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    continue_task9_pending_entry,
)
from services.market_session.policies import MarketSessionPolicy


_STATUSES = frozenset({
    "ALREADY_COMPLETE", "ABSTENTION_PENDING_OBSERVATION", "ENTRY_PENDING",
    "ENTRY_ORPHAN_RECOVERY", "POSITION_ACTIVE", "TERMINAL_UNRECONCILED",
    "PUBLICATION_INCOMPLETE", "RECOVERED", "BLOCKED_CORRUPT_STATE",
})


@dataclass(frozen=True, slots=True)
class Task9RestartRecoveryResultV1:
    prediction_id: str
    status: str
    detail: str
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self):
        if type(self.prediction_id) is not str or not self.prediction_id.strip():
            raise ValueError("prediction_id")
        if self.status not in _STATUSES:
            raise ValueError("status")
        if self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible:
            raise ValueError("PAPER-only recovery result")


class Task9RestartRecoveryDispatcher:
    """Dispatch persisted Task 9 facts; it never fetches or fabricates evidence."""

    def __init__(
        self, *, official_run_id, prediction_ledger, lifecycle_context_store,
        observation_store, pending_entry_store, binding_store,
        outcome_store, reconciliation_store, trade_persistence_service,
        portfolio_persistence_service, terminal_recovery: Callable | None = None,
        session_policy=MarketSessionPolicy(),
    ):
        self.official_run_id = official_run_id
        self.prediction_ledger = prediction_ledger
        self.lifecycle_context_store = lifecycle_context_store
        self.observation_store = observation_store
        self.pending_entry_store = pending_entry_store
        self.binding_store = binding_store
        self.outcome_store = outcome_store
        self.reconciliation_store = reconciliation_store
        self.trade_persistence_service = trade_persistence_service
        self.portfolio_persistence_service = portfolio_persistence_service
        self.terminal_recovery = terminal_recovery
        self.session_policy = session_policy
        if type(official_run_id) is not str or not official_run_id.strip():
            raise ValueError("official_run_id")

    def recover(self, *, prediction_id: str, evaluated_at: datetime) -> Task9RestartRecoveryResultV1:
        """Classify then replay only deterministic existing durable authorities."""
        try:
            if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
                raise ValueError("evaluated_at")
            prediction = self.prediction_ledger.recover(prediction_id)
            if prediction is None:
                raise ValueError("prediction missing")
            pending = self.pending_entry_store.recover(prediction_id)
            binding = self.binding_store.by_prediction(prediction_id)
            outcome = self.outcome_store.recover(prediction_id)
            reconciliation = self.reconciliation_store.recover(prediction_id)

            if prediction.predicted_action in {"WAIT", "NO_TRADE"}:
                context = recover_or_reconstruct_task9_lifecycle_context(
                    prediction=prediction,
                    lifecycle_context_store=self.lifecycle_context_store,
                    session_policy=self.session_policy,
                )
                if binding is not None or pending is not None:
                    raise ValueError("abstention has executed lifecycle state")
                if outcome is not None and reconciliation is not None:
                    return self._result(prediction_id, "ALREADY_COMPLETE", "abstention complete")
                return self._result(prediction_id, "ABSTENTION_PENDING_OBSERVATION", context.persistence_status)

            if pending is not None and pending.status == "WAITING_FOR_ENTRY":
                snapshot = self.trade_persistence_service.get(pending.input_value.paper_trade_id)
                if snapshot is None:
                    return self._result(prediction_id, "ENTRY_PENDING", "durable pending entry")
                recovered = continue_task9_pending_entry(
                    official_run_id=self.official_run_id, prediction_id=prediction_id,
                    observation=pending.input_value.observation, evaluated_at=evaluated_at,
                    pending_entry_store=self.pending_entry_store,
                    trade_persistence_service=self.trade_persistence_service,
                    portfolio_persistence_service=self.portfolio_persistence_service,
                    binding_store=self.binding_store,
                )
                if recovered.status != "OPEN":
                    raise ValueError("pending recovery did not open")
                return self._result(prediction_id, "RECOVERED", "P7/P8/binding replayed")

            if binding is None:
                if outcome is not None or reconciliation is not None:
                    raise ValueError("unbound terminal lifecycle facts")
                return self._result(prediction_id, "PUBLICATION_INCOMPLETE", "binding unavailable")
            snapshot = self.trade_persistence_service.get(binding.paper_trade_id)
            if snapshot is None or snapshot.position is None:
                raise ValueError("binding references unknown P7 trade")
            if (
                binding.market != snapshot.position.underlying_symbol
                or binding.paper_position_id != snapshot.position.position_id
                or binding.option_symbol != snapshot.position.option_symbol
            ):
                raise ValueError("binding/P7 identity mismatch")
            state = snapshot.lifecycle_state.current_state
            if state in {"OPEN", "PARTIALLY_EXITED"}:
                return self._result(prediction_id, "POSITION_ACTIVE", state)
            if state.startswith("CLOSED_") or state in {"CANCELLED", "BLOCKED"}:
                if outcome is not None and reconciliation is not None:
                    return self._result(prediction_id, "ALREADY_COMPLETE", "terminal complete")
                if self.terminal_recovery is not None:
                    self.terminal_recovery(prediction_id=prediction_id, evaluated_at=evaluated_at)
                    return self._result(prediction_id, "RECOVERED", "terminal authority dispatched")
                return self._result(prediction_id, "TERMINAL_UNRECONCILED", state)
            raise ValueError("unsupported P7 lifecycle state")
        except (KeyError, TypeError, ValueError) as exc:
            return self._result(prediction_id, "BLOCKED_CORRUPT_STATE", str(exc))

    @staticmethod
    def _result(prediction_id, status, detail):
        return Task9RestartRecoveryResultV1(prediction_id, status, detail)

