"""Production-only composition for the final Task 9 PAPER child authority.

The composition deliberately receives already-retained current-cycle evidence.
It performs no provider acquisition and it does not implement P6, P7, or P8;
those remain the existing certified authorities invoked through exact delegates.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.certification.task9_cycle_market_evidence_handoff import (
    Task9CycleMarketEvidenceV1,
)
from services.certification.task9_context_evidence_receipt_store import (
    Task9ContextEvidenceReceiptStore,
)
from services.certification.task9_live_decision_audit import (
    Task9LiveDecisionAuditStore,
    build_task9_live_decision_audit,
)
from services.contracts.task9_context_evidence_receipt_v1 import (
    build_task9_context_evidence_receipt,
)
from services.certification.task9_live_paper_certification_runner import (
    Task9LivePaperCertificationRunner,
)
from services.certification.task9_paper_portfolio_policy_store import (
    Task9PaperPortfolioPolicyStore,
)
from services.certification.task9_position_monitoring_runtime import (
    execute_task9_position_monitoring,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_lifecycle_outcome_store import (
    Task9PredictionLifecycleOutcomeStore,
)
from services.certification.task9_prediction_lifecycle_reconciliation_store import (
    Task9PredictionLifecycleReconciliationStore,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
)
from services.certification.task9_pending_entry_store import Task9PendingEntryStore
from services.certification.task9_open_position_monitoring_controller import Task9OpenPositionMonitoringController
from services.certification.task9_certification_publication import Task9CertificationPublicationAuthority
from services.certification.task9_production_child_evidence_authority import (
    build_task9_production_child_authority,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    continue_task9_pending_entry,
    execute_task9_selected_market_lifecycle,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.paper_orchestration.continuous_position_monitoring_runtime import (
    execute_continuous_position_monitoring,
)
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.contracts.task9_run_classification_v1 import validate_task9_run_classification
from services.market_session.policies import MarketSessionPolicy


_MARKETS = (("NIFTY", "NSE"), ("SENSEX", "BSE"))


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    return value.strip()


@dataclass(frozen=True, slots=True)
class Task9ProductionPersistenceLayoutV1:
    """Canonical durable paths for every Task 9 production authority."""

    root: Path
    prediction_ledger_path: Path
    binding_store_path: Path
    lifecycle_context_store_path: Path
    observation_window_store_path: Path
    lifecycle_outcome_store_path: Path
    lifecycle_reconciliation_store_path: Path
    portfolio_policy_store_path: Path
    paper_trade_repository_path: Path
    paper_portfolio_repository_path: Path
    pending_entry_store_path: Path
    context_evidence_receipt_store_path: Path

    @classmethod
    def from_root(
        cls,
        persistence_root: str | Path,
    ) -> "Task9ProductionPersistenceLayoutV1":
        root = Path(persistence_root)
        if not str(root).strip():
            raise ValueError("persistence_root")
        return cls(
            root=root,
            prediction_ledger_path=root / "prediction-ledger.json",
            binding_store_path=root / "prediction-paper-bindings.json",
            lifecycle_context_store_path=root / "prediction-lifecycle-context.json",
            observation_window_store_path=root / "prediction-observation-windows.json",
            lifecycle_outcome_store_path=root / "prediction-lifecycle-outcomes.json",
            lifecycle_reconciliation_store_path=(
                root / "prediction-lifecycle-reconciliations.json"
            ),
            portfolio_policy_store_path=root / "paper-portfolio-policies.json",
            paper_trade_repository_path=root / "p7-trades.json",
            paper_portfolio_repository_path=root / "p8-portfolios.json",
            pending_entry_store_path=root / "pending-paper-entries.json",
            context_evidence_receipt_store_path=(
                root / "context-evidence-receipts.json"
            ),
        )


@dataclass(frozen=True, slots=True)
class Task9LivePaperProductionRuntimeV1:
    """Boundary-locked runner and all services rooted in one directory."""

    persistence_layout: Task9ProductionPersistenceLayoutV1
    runner: Task9LivePaperCertificationRunner
    child_authority: Callable
    evaluated_at: datetime
    prediction_ledger: PredictionLedger
    binding_store: Task9PredictionPaperTradeBindingStore
    lifecycle_context_store: Task9PredictionLifecycleContextStore
    observation_store: Task9PredictionObservationWindowStore
    outcome_store: Task9PredictionLifecycleOutcomeStore
    reconciliation_store: Task9PredictionLifecycleReconciliationStore
    portfolio_policy_store: Task9PaperPortfolioPolicyStore
    trade_persistence_service: PaperTradePersistenceService
    portfolio_persistence_service: PaperPortfolioPersistenceService
    pending_entry_store: Task9PendingEntryStore
    context_evidence_receipt_store: Task9ContextEvidenceReceiptStore
    outcome_policy: PredictionLifecycleOutcomePolicyV1
    portfolio_id: str
    publication_authority: Task9CertificationPublicationAuthority
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        _aware(self.evaluated_at, "evaluated_at")
        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError("PAPER-only Task 9 production runtime")

    def run_cycle(self, *, cycle_id: str, evaluated_at: datetime):
        """Run only at the evidence boundary used to build this authority."""

        boundary = _aware(evaluated_at, "evaluated_at")
        if boundary != self.evaluated_at:
            raise ValueError("cycle boundary does not match retained evidence")
        result = self.runner.run_cycle(
            cycle_id=cycle_id,
            evaluated_at=boundary,
        )
        self.publication_authority.refresh(session_date=boundary.date(), evaluated_at=boundary)
        return result

    def continue_pending_entry(self, *, prediction_id: str, observation, evaluated_at: datetime):
        """Continue only a previously durable selected PAPER entry authority."""
        return continue_task9_pending_entry(
            official_run_id=self.runner.official_run_id,
            prediction_id=prediction_id,
            observation=observation,
            evaluated_at=_aware(evaluated_at, "evaluated_at"),
            pending_entry_store=self.pending_entry_store,
            trade_persistence_service=self.trade_persistence_service,
            portfolio_persistence_service=self.portfolio_persistence_service,
            binding_store=self.binding_store,
        )

    def monitor_open_positions(self, *, observation_provider, evaluated_at: datetime, iterations: int = 1, cadence_seconds: float = 0.0, sleep=None, clock=None):
        """Monitor every durable Task9-bound OPEN/PARTIALLY_EXITED PAPER position."""
        def monitoring_kwargs(*, snapshot, observation, portfolio_policy_id):
            policy = self.portfolio_policy_store.recover(portfolio_policy_id)
            if policy is None:
                raise ValueError("monitoring durable portfolio policy unavailable")
            return _monitor_kwargs(
                official_run_id=self.runner.official_run_id,
                snapshot=snapshot,
                observation=observation,
                portfolio_id=self.portfolio_id,
                portfolio_policy=policy,
                portfolio_persistence_service=self.portfolio_persistence_service,
                trade_persistence_service=self.trade_persistence_service,
            )
        controller = Task9OpenPositionMonitoringController(
            official_run_id=self.runner.official_run_id,
            portfolio_id=self.portfolio_id,
            prediction_ledger=self.prediction_ledger,
            binding_store=self.binding_store,
            lifecycle_context_store=self.lifecycle_context_store,
            observation_store=self.observation_store,
            outcome_store=self.outcome_store,
            reconciliation_store=self.reconciliation_store,
            outcome_policy=self.outcome_policy,
            portfolio_persistence_service=self.portfolio_persistence_service,
            trade_persistence_service=self.trade_persistence_service,
            monitor_kwargs_factory=monitoring_kwargs,
            on_terminal_reconciled=lambda at: self.publication_authority.refresh(session_date=at.date(), evaluated_at=at),
        )
        kwargs = {"observation_provider": observation_provider, "evaluated_at": _aware(evaluated_at, "evaluated_at"), "iterations": iterations, "cadence_seconds": cadence_seconds, "clock": clock}
        if sleep is not None: kwargs["sleep"] = sleep
        return controller.run(**kwargs)


def _monitor_kwargs(
    *,
    official_run_id: str,
    snapshot: PaperTradePersistenceSnapshotV1,
    observation,
    portfolio_id: str,
    portfolio_policy,
    portfolio_persistence_service: PaperPortfolioPersistenceService,
    trade_persistence_service: PaperTradePersistenceService,
) -> dict[str, object]:
    """Build deterministic monitor IDs from immutable cycle evidence only."""

    prefix = (
        f"task9-monitor:{official_run_id}:{snapshot.paper_trade_id}:"
        f"{observation.observation_id}"
    )
    return {
        "portfolio_id": portfolio_id,
        "paper_trade_id": snapshot.paper_trade_id,
        "portfolio_policy": portfolio_policy,
        "observation": observation,
        "evaluation_timestamp": observation.observed_at,
        "requested_transition_id": f"{prefix}:transition",
        "resulting_lifecycle_state_id": f"{prefix}:state",
        "evaluation_result_id": f"{prefix}:evaluation",
        "exit_fill_ids": tuple(
            f"{prefix}:exit:{index}"
            for index in range(1, 5)
        ),
        "pnl_evidence_id": f"{prefix}:pnl",
        "result_snapshot_id": f"{prefix}:portfolio-snapshot",
        "portfolio_event_id": f"{prefix}:portfolio-event",
        "update_idempotency_key": f"{prefix}:update",
        "portfolio_persistence_service": portfolio_persistence_service,
        "trade_persistence_service": trade_persistence_service,
    }


def build_task9_live_paper_production_runtime(
    *,
    official_run_id: str,
    run_classification: str = "OFFICIAL_CERTIFICATION",
    official_start_at: datetime,
    evaluated_at: datetime,
    persistence_root: str | Path,
    cycle_evidence_by_market: Mapping[
        tuple[str, str],
        Task9CycleMarketEvidenceV1,
    ],
    available_capital: float,
    portfolio_id: str,
    outcome_policy: PredictionLifecycleOutcomePolicyV1,
    session_policy: MarketSessionPolicy = MarketSessionPolicy(),
    persist: Callable,
    publish: Callable | None = None,
) -> Task9LivePaperProductionRuntimeV1:
    """Bind one exact two-market evidence map to the existing Task 9 runner."""

    run_id = _text(official_run_id, "official_run_id")
    classification = validate_task9_run_classification(run_classification)
    start_at = _aware(official_start_at, "official_start_at")
    boundary = _aware(evaluated_at, "evaluated_at")
    portfolio = _text(portfolio_id, "portfolio_id")
    if (
        type(available_capital) not in (int, float)
        or isinstance(available_capital, bool)
        or available_capital <= 0
    ):
        raise ValueError("available_capital")
    if type(outcome_policy) is not PredictionLifecycleOutcomePolicyV1:
        raise TypeError("outcome_policy")
    if type(session_policy) is not MarketSessionPolicy:
        raise TypeError("session_policy")
    if not callable(persist) or (publish is not None and not callable(publish)):
        raise TypeError("runner persistence")

    ordered_evidence = tuple(
        cycle_evidence_by_market.get(identity)
        for identity in _MARKETS
    )
    if any(type(item) is not Task9CycleMarketEvidenceV1 for item in ordered_evidence):
        raise ValueError("exact two-market cycle evidence is required")
    if any(item.lifecycle_window is None for item in ordered_evidence):
        raise ValueError("exact lifecycle windows are required")

    layout = Task9ProductionPersistenceLayoutV1.from_root(
        persistence_root
    )
    prediction_ledger = PredictionLedger(layout.prediction_ledger_path)
    binding_store = Task9PredictionPaperTradeBindingStore(
        layout.binding_store_path
    )
    lifecycle_context_store = Task9PredictionLifecycleContextStore(
        layout.lifecycle_context_store_path
    )
    observation_store = Task9PredictionObservationWindowStore(
        layout.observation_window_store_path
    )
    outcome_store = Task9PredictionLifecycleOutcomeStore(
        layout.lifecycle_outcome_store_path
    )
    reconciliation_store = Task9PredictionLifecycleReconciliationStore(
        layout.lifecycle_reconciliation_store_path
    )
    portfolio_policy_store = Task9PaperPortfolioPolicyStore(
        layout.portfolio_policy_store_path
    )
    trade_persistence_service = PaperTradePersistenceService(
        PaperTradeRepository(layout.paper_trade_repository_path)
    )
    portfolio_persistence_service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(layout.paper_portfolio_repository_path)
    )
    pending_entry_store = Task9PendingEntryStore(layout.pending_entry_store_path)
    context_evidence_receipt_store = Task9ContextEvidenceReceiptStore(
        layout.context_evidence_receipt_store_path
    )
    decision_audit_store = Task9LiveDecisionAuditStore(
        layout.root / "live-decision-audit.json"
    )
    publication_authority = Task9CertificationPublicationAuthority(
        official_run_id=run_id,
        run_classification=classification,
        official_start_at=start_at,
        root=layout.root,
        prediction_ledger=prediction_ledger,
        binding_store=binding_store,
        outcome_store=outcome_store,
        reconciliation_store=reconciliation_store,
        trade_persistence_service=trade_persistence_service,
        starting_capital=float(available_capital),
    )
    for item in ordered_evidence:
        evaluation = item.evaluation
        canonical_evidence = (
            None
            if evaluation is None
            else evaluation.evidence
        )

        broader_market = (
            None
            if canonical_evidence is None
            else canonical_evidence.broader_market
        )

        external_context = (
            None
            if canonical_evidence is None
            else canonical_evidence.external_context
        )

        receipt = build_task9_context_evidence_receipt(
            receipt_id=(
                f"task9-context:{run_id}:"
                f"{item.prediction.prediction_id}"
            ),
            official_run_id=run_id,
            parent_cycle_id=(
                item.prediction.parent_cycle_id
            ),
            prediction_id=(
                item.prediction.prediction_id
            ),
            observation_id=(
                item.cycle.observation_id
            ),
            underlying_symbol=(
                item.prediction.underlying_symbol
            ),
            exchange=(
                item.prediction.exchange
            ),
            evaluated_at=boundary,
            broader_market=broader_market,
            external_context=external_context,
            external_provider_snapshot_id=None,
        )

        context_evidence_receipt_store.save(
            receipt
        )

        recovered_receipt = (
            context_evidence_receipt_store.recover(
                item.prediction.prediction_id
            )
        )

        if recovered_receipt != receipt:
            raise ValueError(
                "durable context evidence receipt identity"
            )

        decision_audit = build_task9_live_decision_audit(
            audit_id=(
                f"task9-decision-audit:{run_id}:"
                f"{item.prediction.prediction_id}"
            ),
            official_run_id=run_id,
            parent_cycle_id=(
                item.prediction.parent_cycle_id
            ),
            prediction_id=(
                item.prediction.prediction_id
            ),
            observation_id=(
                item.cycle.observation_id
            ),
            underlying_symbol=(
                item.prediction.underlying_symbol
            ),
            exchange=(
                item.prediction.exchange
            ),
            evaluated_at=boundary,
            evaluation=evaluation,
            prediction_action=getattr(
                item.prediction,
                "predicted_action",
                getattr(
                    item.prediction,
                    "action",
                    None,
                ),
            ),
            prediction_direction=getattr(
                item.prediction,
                "predicted_direction",
                getattr(
                    item.prediction,
                    "direction",
                    None,
                ),
            ),
            prediction_eligibility=getattr(
                item.prediction,
                "eligibility",
                None,
            ),
            prediction_blockers=tuple(
                item.prediction.blockers
            ),
            selected_planning=(
                item.selected_planning
            ),
            paper_observation=(
                item.paper_observation
            ),
            provider_incident_ids=tuple(
                incident.incident_id
                for incident
                in item.provider_incidents
            ),
            failure_diagnostic=getattr(
                item.prediction,
                "failure_diagnostic",
                None,
            ),
        )

        decision_audit_store.save(
            decision_audit
        )

        recovered_decision_audit = (
            decision_audit_store.recover(
                item.prediction.prediction_id
            )
        )

        if (
            recovered_decision_audit
            != decision_audit
        ):
            raise ValueError(
                "durable Task 9 live decision audit identity"
            )

    prediction_ledger.save_pair(tuple(
        item.prediction for item in ordered_evidence
    ))
    for item in ordered_evidence:
        assert item.lifecycle_window is not None
        lifecycle_context_store.save(item.lifecycle_window)

        # Only a completed, available-evidence WAIT/NO_TRADE prediction
        # is a genuine Task 9 abstention. FAILED children and completed
        # provider/data incidents must remain outside the abstention window
        # lifecycle even when their fallback action is WAIT/NO_TRADE.
        is_genuine_abstention = (
            item.prediction.terminal_status == "COMPLETED"
            and item.prediction.eligibility != "UNAVAILABLE"
            and item.prediction.predicted_action in {"WAIT", "NO_TRADE"}
        )
        if is_genuine_abstention:
            observation_store.initialize(
                prediction=item.prediction,
                entry_window_ends_at=(
                    item.lifecycle_window.entry_window_ends_at
                ),
                validity_window_ends_at=(
                    item.lifecycle_window.validity_window_ends_at
                ),
            )
    def entry_delegate(
        evidence: Task9CycleMarketEvidenceV1,
        prediction_id: str,
    ):
        if prediction_id != evidence.prediction.prediction_id:
            raise ValueError("entry prediction identity")
        # A durable pending entry owns this prediction until it opens or reaches
        # a terminal entry outcome; never rebuild P6/P8 merely to poll a zone.
        if pending_entry_store.recover(prediction_id) is not None:
            return pending_entry_store.recover(prediction_id)
        if evidence.selected_planning is None:
            raise ValueError("selected planning is required for Task 9 entry")
        return execute_task9_selected_market_lifecycle(
            official_run_id=run_id,
            binding_store=binding_store,
            prediction_id=prediction_id,
            prediction_ledger=prediction_ledger,
            lifecycle_context_store=lifecycle_context_store,
            observation_store=observation_store,
            portfolio_policy_store=portfolio_policy_store,
            selected_cycle=evidence.cycle,
            selected_planning=evidence.selected_planning,
            available_capital=float(available_capital),
            evaluated_at=boundary,
            persistence_root=layout.root,
            portfolio_id=portfolio,
            pending_entry_store=pending_entry_store,
        )

    def monitoring_delegate(
        evidence: Task9CycleMarketEvidenceV1,
        snapshot: PaperTradePersistenceSnapshotV1,
        observation,
    ):
        recovered = trade_persistence_service.get(
            snapshot.paper_trade_id
        )
        if recovered != snapshot:
            raise ValueError("monitoring durable snapshot identity")
        portfolio_snapshot = portfolio_persistence_service.get(portfolio)
        if portfolio_snapshot is None:
            raise ValueError("monitoring durable portfolio unavailable")
        policy = portfolio_policy_store.recover(
            portfolio_snapshot.portfolio_snapshot.portfolio_policy_id
        )
        if policy is None:
            raise ValueError("monitoring durable portfolio policy unavailable")
        if observation is not evidence.paper_observation:
            raise ValueError("monitoring exact observation identity")
        return execute_task9_position_monitoring(
            recovered_snapshot=snapshot,
            observation=observation,
            prediction_ledger=prediction_ledger,
            binding_store=binding_store,
            lifecycle_context_store=lifecycle_context_store,
            observation_store=observation_store,
            monitor=execute_continuous_position_monitoring,
            monitor_kwargs=_monitor_kwargs(
                official_run_id=run_id,
                snapshot=snapshot,
                observation=observation,
                portfolio_id=portfolio,
                portfolio_policy=policy,
                portfolio_persistence_service=portfolio_persistence_service,
                trade_persistence_service=trade_persistence_service,
            ),
        )

    child_authority = build_task9_production_child_authority(
        official_run_id=run_id,
        cycle_evidence_by_market=cycle_evidence_by_market,
        evaluated_at=boundary,
        prediction_ledger=prediction_ledger,
        binding_store=binding_store,
        trade_persistence_service=trade_persistence_service,
        lifecycle_context_store=lifecycle_context_store,
        observation_store=observation_store,
        outcome_store=outcome_store,
        reconciliation_store=reconciliation_store,
        outcome_policy=outcome_policy,
        session_policy=session_policy,
        entry_delegate=entry_delegate,
        monitoring_delegate=monitoring_delegate,
    )
    runner = Task9LivePaperCertificationRunner(
        official_run_id=run_id,
        official_start_at=start_at,
        run_classification=classification,
        child_authority=child_authority,
        persist=persist,
        publish=publish,
    )
    return Task9LivePaperProductionRuntimeV1(
        persistence_layout=layout,
        runner=runner,
        child_authority=child_authority,
        evaluated_at=boundary,
        prediction_ledger=prediction_ledger,
        binding_store=binding_store,
        lifecycle_context_store=lifecycle_context_store,
        observation_store=observation_store,
        outcome_store=outcome_store,
        reconciliation_store=reconciliation_store,
        portfolio_policy_store=portfolio_policy_store,
        trade_persistence_service=trade_persistence_service,
        portfolio_persistence_service=portfolio_persistence_service,
        pending_entry_store=pending_entry_store,
        context_evidence_receipt_store=context_evidence_receipt_store,
        outcome_policy=outcome_policy,
        portfolio_id=portfolio,
        publication_authority=publication_authority,
    )
