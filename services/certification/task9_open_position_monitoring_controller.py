"""Task 9 unattended monitor for durable, bound PAPER positions only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import sleep as _sleep

from services.certification.task9_position_monitoring_runtime import execute_task9_position_monitoring
from services.certification.task9_prediction_lifecycle_context_store import Task9PredictionLifecycleContextStore
from services.certification.task9_prediction_lifecycle_outcome_store import Task9PredictionLifecycleOutcomeStore
from services.certification.task9_prediction_lifecycle_reconciliation_store import Task9PredictionLifecycleReconciliationStore
from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore
from services.contracts.paper_market_observation_v1 import PaperMarketObservationV1
from services.contracts.prediction_lifecycle_outcome_input_v1 import PredictionLifecycleOutcomeInputV1
from services.contracts.prediction_lifecycle_outcome_policy_v1 import PredictionLifecycleOutcomePolicyV1
from services.paper_orchestration.continuous_position_monitoring_runtime import execute_continuous_position_monitoring
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_portfolio.paper_portfolio_persistence_service import PaperPortfolioPersistenceService
from services.paper_trading.paper_trade_persistence_service import PaperTradePersistenceService
from services.prediction_outcomes.prediction_lifecycle_outcome_evaluator import evaluate_prediction_lifecycle_outcome
from services.prediction_outcomes.prediction_lifecycle_reconciliation_service import reconcile_prediction_lifecycle


@dataclass(frozen=True, slots=True)
class Task9OpenPositionMonitoringIterationV1:
    paper_trade_id: str
    prediction_id: str
    status: str
    terminal_reconciled: bool
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    def __post_init__(self):
        if not all(type(item) is str and item for item in (self.paper_trade_id, self.prediction_id, self.status)) or self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible: raise ValueError("PAPER monitoring iteration")


class Task9OpenPositionMonitoringController:
    """Discovers active Task9 bindings and monitors each once per supplied tick."""
    def __init__(self, *, official_run_id: str, portfolio_id: str, prediction_ledger: PredictionLedger, binding_store: Task9PredictionPaperTradeBindingStore, lifecycle_context_store: Task9PredictionLifecycleContextStore, observation_store: Task9PredictionObservationWindowStore, outcome_store: Task9PredictionLifecycleOutcomeStore, reconciliation_store: Task9PredictionLifecycleReconciliationStore, outcome_policy: PredictionLifecycleOutcomePolicyV1, portfolio_persistence_service: PaperPortfolioPersistenceService, trade_persistence_service: PaperTradePersistenceService, monitor_kwargs_factory, on_terminal_reconciled=None):
        if type(official_run_id) is not str or not official_run_id.strip() or type(portfolio_id) is not str or not portfolio_id.strip() or not callable(monitor_kwargs_factory): raise ValueError("controller identity")
        if type(prediction_ledger) is not PredictionLedger or type(binding_store) is not Task9PredictionPaperTradeBindingStore or type(lifecycle_context_store) is not Task9PredictionLifecycleContextStore or type(observation_store) is not Task9PredictionObservationWindowStore or type(outcome_store) is not Task9PredictionLifecycleOutcomeStore or type(reconciliation_store) is not Task9PredictionLifecycleReconciliationStore or type(outcome_policy) is not PredictionLifecycleOutcomePolicyV1 or type(portfolio_persistence_service) is not PaperPortfolioPersistenceService or type(trade_persistence_service) is not PaperTradePersistenceService: raise TypeError("controller dependencies")
        self.official_run_id, self.portfolio_id = official_run_id.strip(), portfolio_id.strip()
        self.prediction_ledger, self.binding_store, self.lifecycle_context_store, self.observation_store = prediction_ledger, binding_store, lifecycle_context_store, observation_store
        self.outcome_store, self.reconciliation_store, self.outcome_policy = outcome_store, reconciliation_store, outcome_policy
        if on_terminal_reconciled is not None and not callable(on_terminal_reconciled): raise TypeError("on_terminal_reconciled")
        self.portfolio_persistence_service, self.trade_persistence_service, self.monitor_kwargs_factory, self.on_terminal_reconciled = portfolio_persistence_service, trade_persistence_service, monitor_kwargs_factory, on_terminal_reconciled

    def discover(self):
        values = []
        for binding in self.binding_store.list_all():
            if binding.official_run_id != self.official_run_id: continue
            snapshot = self.trade_persistence_service.get(binding.paper_trade_id)
            if snapshot is None: continue
            if snapshot.position is None or snapshot.position.option_symbol != binding.option_symbol or snapshot.position.underlying_symbol != binding.market: raise ValueError("durable binding position identity")
            if snapshot.lifecycle_state.is_terminal:
                if self.reconciliation_store.recover(binding.prediction_id) is None:
                    values.append((binding, snapshot))
                continue
            if snapshot.lifecycle_state.current_state not in {"OPEN", "PARTIALLY_EXITED"}: continue
            values.append((binding, snapshot))
        return tuple(values)

    def _reconcile_terminal(self, binding, snapshot, evaluated_at):
        prediction = self.prediction_ledger.recover(binding.prediction_id); window = self.observation_store.recover(binding.prediction_id)
        if prediction is None or window is None: raise ValueError("terminal Task9 lifecycle evidence unavailable")
        outcome = evaluate_prediction_lifecycle_outcome(PredictionLifecycleOutcomeInputV1(prediction=prediction, observation_window=window, policy=self.outcome_policy, evaluated_at=evaluated_at))
        existing = self.outcome_store.recover(prediction.prediction_id)
        if existing is None: self.outcome_store.save(outcome)
        elif existing != outcome: raise ValueError("conflicting terminal lifecycle outcome")
        outcome = self.outcome_store.recover(prediction.prediction_id)
        reconciliation = reconcile_prediction_lifecycle(prediction=prediction, outcome=outcome, position=snapshot.position, reconciled_at=evaluated_at, pnl_evidence=snapshot.pnl_evidence)
        existing = self.reconciliation_store.recover(prediction.prediction_id)
        if existing is None: self.reconciliation_store.save(reconciliation)
        elif existing != reconciliation: raise ValueError("conflicting terminal lifecycle reconciliation")
        return reconciliation.status == "RECONCILED"

    def run_once(self, *, observation_provider, evaluated_at: datetime):
        if not callable(observation_provider) or not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None: raise ValueError("monitoring iteration")
        results = []
        for binding, snapshot in self.discover():
            if snapshot.lifecycle_state.is_terminal:
                reconciled = self._reconcile_terminal(binding, snapshot, evaluated_at)
                if reconciled and self.on_terminal_reconciled is not None: self.on_terminal_reconciled(evaluated_at)
                results.append(Task9OpenPositionMonitoringIterationV1(snapshot.paper_trade_id, binding.prediction_id, "TERMINAL_RECOVERED", reconciled))
                continue
            try:
                observation = observation_provider(binding, snapshot)
            except Exception:
                results.append(Task9OpenPositionMonitoringIterationV1(snapshot.paper_trade_id, binding.prediction_id, "OBSERVATION_UNAVAILABLE", False))
                continue
            if type(observation) is not PaperMarketObservationV1: raise TypeError("observation_provider must return PaperMarketObservationV1")
            if (observation.market, observation.option_symbol) != (binding.market, binding.option_symbol): raise ValueError("observation binding identity")
            portfolio_snapshot = self.portfolio_persistence_service.get(self.portfolio_id)
            if portfolio_snapshot is None: raise ValueError("durable portfolio unavailable")
            policy = portfolio_snapshot.portfolio_snapshot.portfolio_policy_id
            kwargs = self.monitor_kwargs_factory(snapshot=snapshot, observation=observation, portfolio_policy_id=policy)
            result = execute_task9_position_monitoring(recovered_snapshot=snapshot, observation=observation, prediction_ledger=self.prediction_ledger, binding_store=self.binding_store, lifecycle_context_store=self.lifecycle_context_store, observation_store=self.observation_store, monitor=execute_continuous_position_monitoring, monitor_kwargs=kwargs)
            after = self.trade_persistence_service.get(snapshot.paper_trade_id)
            if after is None: raise ValueError("monitored snapshot unavailable")
            terminal = after.lifecycle_state.is_terminal
            reconciled = self._reconcile_terminal(binding, after, evaluated_at) if terminal else False
            if reconciled and self.on_terminal_reconciled is not None: self.on_terminal_reconciled(evaluated_at)
            results.append(Task9OpenPositionMonitoringIterationV1(snapshot.paper_trade_id, binding.prediction_id, result.monitoring_status, reconciled))
        return tuple(results)

    def run(self, *, observation_provider, evaluated_at, iterations: int = 1, cadence_seconds: float = 0.0, sleep=_sleep, clock=None):
        if type(iterations) is not int or iterations < 1 or type(cadence_seconds) not in (int, float) or cadence_seconds < 0 or not callable(sleep): raise ValueError("cadence")
        current = evaluated_at; values = []
        for index in range(iterations):
            values.append(self.run_once(observation_provider=observation_provider, evaluated_at=current))
            if index + 1 < iterations:
                sleep(cadence_seconds)
                if clock is not None: current = clock()
        return tuple(values)
