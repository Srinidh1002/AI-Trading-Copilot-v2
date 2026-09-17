"""Canonical deterministic Task 9 restart recovery before fresh parent cycles."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.certification.task9_abstention_later_observation_recovery import (
    finalize_task9_expired_abstentions,
)
from services.certification.task9_certification_publication import (
    Task9CertificationPublicationAuthority,
)
from services.certification.task9_live_paper_production_composition import (
    Task9ProductionPersistenceLayoutV1,
)
from services.certification.task9_open_position_monitoring_controller import (
    recover_task9_terminal_prediction,
)
from services.certification.task9_pending_entry_store import (
    Task9PendingEntryStore,
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
from services.certification.task9_restart_recovery_dispatcher import (
    Task9RestartRecoveryDispatcher,
    Task9RestartRecoveryResultV1,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import (
    PaperPortfolioRepository,
)
from services.paper_trade_repository import (
    PaperTradeRepository,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.prediction_outcomes.prediction_lifecycle_reconciliation_service import (
    reconcile_prediction_lifecycle,
)


_ABSTENTION_ACTIONS = frozenset(
    {"WAIT", "NO_TRADE"}
)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _prediction_ids(
    prediction_ledger: PredictionLedger,
) -> tuple[str, ...]:
    values: set[str] = set()

    for raw in prediction_ledger.all_records():
        if type(raw) is not dict:
            raise ValueError(
                "invalid durable Task9 prediction record"
            )

        prediction_id = raw.get("prediction_id")
        if (
            type(prediction_id) is not str
            or not prediction_id.strip()
        ):
            raise ValueError(
                "invalid durable Task9 prediction identity"
            )

        values.add(prediction_id.strip())

    return tuple(sorted(values))


def _reconcile_durable_abstention_outcomes(
    *,
    prediction_ids: tuple[str, ...],
    prediction_ledger: PredictionLedger,
    outcome_store: Task9PredictionLifecycleOutcomeStore,
    reconciliation_store: Task9PredictionLifecycleReconciliationStore,
    evaluated_at: datetime,
) -> tuple[str, ...]:
    reconciled: list[str] = []

    for prediction_id in prediction_ids:
        prediction = prediction_ledger.recover(
            prediction_id
        )
        if prediction is None:
            raise ValueError(
                "durable Task9 prediction disappeared"
            )

        if (
            prediction.predicted_action
            not in _ABSTENTION_ACTIONS
        ):
            continue

        outcome = outcome_store.recover(
            prediction_id
        )
        if outcome is None:
            continue

        existing = reconciliation_store.recover(
            prediction_id
        )
        if existing is not None:
            continue

        reconciliation = reconcile_prediction_lifecycle(
            prediction=prediction,
            outcome=outcome,
            position=None,
            reconciled_at=evaluated_at,
        )

        reconciliation_store.save(
            reconciliation
        )

        recovered = reconciliation_store.recover(
            prediction_id
        )
        if recovered != reconciliation:
            raise ValueError(
                "durable abstention reconciliation recovery"
            )

        reconciled.append(prediction_id)

    return tuple(reconciled)


def run_task9_restart_recovery_startup(
    *,
    official_run_id: str,
    official_start_at: datetime,
    persistence_root: str | Path,
    evaluated_at: datetime,
    starting_capital: float,
    run_classification: str,
    live_stream_root: str | Path | None = None,
) -> tuple[Task9RestartRecoveryResultV1, ...]:
    """Recover durable Task 9 lifecycle state before any fresh parent evidence."""

    if (
        type(official_run_id) is not str
        or not official_run_id.strip()
    ):
        raise ValueError("official_run_id")

    boundary = _aware(
        evaluated_at,
        "evaluated_at",
    )
    start_at = _aware(
        official_start_at,
        "official_start_at",
    )

    if (
        type(starting_capital) not in (int, float)
        or isinstance(starting_capital, bool)
        or starting_capital <= 0
    ):
        raise ValueError("starting_capital")

    layout = Task9ProductionPersistenceLayoutV1.from_root(
        persistence_root
    )

    prediction_ledger = PredictionLedger(
        layout.prediction_ledger_path
    )
    binding_store = (
        Task9PredictionPaperTradeBindingStore(
            layout.binding_store_path
        )
    )
    lifecycle_context_store = (
        Task9PredictionLifecycleContextStore(
            layout.lifecycle_context_store_path
        )
    )
    observation_store = (
        Task9PredictionObservationWindowStore(
            layout.observation_window_store_path
        )
    )
    outcome_store = (
        Task9PredictionLifecycleOutcomeStore(
            layout.lifecycle_outcome_store_path
        )
    )
    reconciliation_store = (
        Task9PredictionLifecycleReconciliationStore(
            layout.lifecycle_reconciliation_store_path
        )
    )
    pending_entry_store = Task9PendingEntryStore(
        layout.pending_entry_store_path
    )
    trade_persistence_service = (
        PaperTradePersistenceService(
            PaperTradeRepository(
                layout.paper_trade_repository_path
            )
        )
    )
    portfolio_persistence_service = (
        PaperPortfolioPersistenceService(
            PaperPortfolioRepository(
                layout.paper_portfolio_repository_path
            )
        )
    )

    outcome_policy = (
        PredictionLifecycleOutcomePolicyV1(
            policy_id=(
                "task9-production-lifecycle-policy"
            ),
            policy_version="1.0",
        )
    )

    prediction_ids = _prediction_ids(
        prediction_ledger
    )

    if not prediction_ids:
        return ()

    def terminal_recovery(
        *,
        prediction_id: str,
        evaluated_at: datetime,
    ) -> bool:
        binding = binding_store.by_prediction(
            prediction_id
        )
        if binding is None:
            raise ValueError(
                "terminal Task9 binding unavailable"
            )

        snapshot = trade_persistence_service.get(
            binding.paper_trade_id
        )
        if (
            snapshot is None
            or snapshot.position is None
        ):
            raise ValueError(
                "terminal Task9 P7 snapshot unavailable"
            )

        return recover_task9_terminal_prediction(
            prediction_ledger=prediction_ledger,
            observation_store=observation_store,
            outcome_store=outcome_store,
            reconciliation_store=reconciliation_store,
            outcome_policy=outcome_policy,
            binding=binding,
            snapshot=snapshot,
            evaluated_at=evaluated_at,
        )

    dispatcher = Task9RestartRecoveryDispatcher(
        official_run_id=official_run_id,
        prediction_ledger=prediction_ledger,
        lifecycle_context_store=(
            lifecycle_context_store
        ),
        observation_store=observation_store,
        pending_entry_store=pending_entry_store,
        binding_store=binding_store,
        outcome_store=outcome_store,
        reconciliation_store=reconciliation_store,
        trade_persistence_service=(
            trade_persistence_service
        ),
        portfolio_persistence_service=(
            portfolio_persistence_service
        ),
        terminal_recovery=terminal_recovery,
    )

    # Pass 1:
    # - reconstruct abstention lifecycle context,
    # - recover P7/P8/binding entry orphans,
    # - recover already-terminal directional positions,
    # - classify active positions without market reads.
    for prediction_id in prediction_ids:
        dispatcher.recover(
            prediction_id=prediction_id,
            evaluated_at=boundary,
        )

    # Existing provider-free authority. It consumes only already-durable
    # observation windows and never appends a fresh quote.
    finalize_task9_expired_abstentions(
        prediction_ledger=prediction_ledger,
        lifecycle_context_store=(
            lifecycle_context_store
        ),
        observation_store=observation_store,
        outcome_store=outcome_store,
        outcome_policy=outcome_policy,
        evaluated_at=boundary,
        live_stream_root=(
            Path(live_stream_root)
            if live_stream_root is not None
            else Path(persistence_root) / "live_stream"
        ),
    )

    # WAIT / NO_TRADE outcomes are analytics, never PAPER positions.
    # Complete their existing lifecycle reconciliation with position=None.
    _reconcile_durable_abstention_outcomes(
        prediction_ids=prediction_ids,
        prediction_ledger=prediction_ledger,
        outcome_store=outcome_store,
        reconciliation_store=reconciliation_store,
        evaluated_at=boundary,
    )

    # Final deterministic classification after all allowed durable repair.
    results = tuple(
        dispatcher.recover(
            prediction_id=prediction_id,
            evaluated_at=boundary,
        )
        for prediction_id in prediction_ids
    )

    Task9CertificationPublicationAuthority(
        official_run_id=official_run_id,
        official_start_at=start_at,
        root=persistence_root,
        prediction_ledger=prediction_ledger,
        binding_store=binding_store,
        outcome_store=outcome_store,
        reconciliation_store=(
            reconciliation_store
        ),
        trade_persistence_service=(
            trade_persistence_service
        ),
        starting_capital=float(
            starting_capital
        ),
        run_classification=run_classification,
    ).refresh(
        session_date=boundary.date(),
        evaluated_at=boundary,
    )

    return results


__all__ = [
    "run_task9_restart_recovery_startup",
]
