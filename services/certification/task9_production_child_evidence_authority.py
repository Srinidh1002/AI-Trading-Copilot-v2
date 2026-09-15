"""Final PAPER-only Task 9 child evidence authority.

This module owns no provider acquisition and no P7/P8 implementation.  It
coordinates exact evidence already retained by Task 8 with durable Task 9
stores, while delegates invoke the existing entry and monitoring authorities.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import TypeAlias

from services.certification.task9_abstention_prediction_observation_runtime import (
    record_task9_abstention_prediction_observation,
)
from services.certification.task9_abstention_later_observation_recovery import (
    recover_task9_later_abstention_observations,
)
from services.certification.task9_cycle_market_evidence_handoff import (
    Task9CycleMarketEvidenceV1,
)
from services.certification.task9_live_paper_certification_runner import (
    Task9MarketCycleEvidenceV1,
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
from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.prediction_lifecycle_outcome_input_v1 import (
    PredictionLifecycleOutcomeInputV1,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.market_session.policies import MarketSessionPolicy
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.prediction_outcomes.prediction_lifecycle_outcome_evaluator import (
    evaluate_prediction_lifecycle_outcome,
)
from services.prediction_outcomes.prediction_lifecycle_reconciliation_service import (
    reconcile_prediction_lifecycle,
)


MarketIdentity: TypeAlias = tuple[str, str]
EntryDelegate: TypeAlias = Callable[[Task9CycleMarketEvidenceV1, str], object]
MonitoringDelegate: TypeAlias = Callable[
    [
        Task9CycleMarketEvidenceV1,
        PaperTradePersistenceSnapshotV1,
        PaperMarketObservationV1,
    ],
    object,
]

_MARKETS: tuple[MarketIdentity, ...] = (
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
)
_ENTRY_ACTIONS = frozenset({"CALL", "PUT"})
_ABSTENTION_ACTIONS = frozenset({"WAIT", "NO_TRADE"})
_PROVIDER_DATA_INCIDENT_REASONS = frozenset({
    "HISTORICAL-DATA_RATE_LIMITED",
})
logger = logging.getLogger(__name__)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _nonempty(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    return value.strip()


def _freeze_handoffs(
    values: Mapping[MarketIdentity, Task9CycleMarketEvidenceV1],
) -> Mapping[MarketIdentity, Task9CycleMarketEvidenceV1]:
    if not isinstance(values, Mapping):
        raise TypeError("cycle_evidence_by_market")
    copied = dict(values)
    if set(copied) != set(_MARKETS):
        raise ValueError("cycle evidence markets")
    for identity in _MARKETS:
        evidence = copied[identity]
        if type(evidence) is not Task9CycleMarketEvidenceV1:
            raise TypeError("cycle evidence")
        prediction = evidence.prediction
        if (
            prediction.underlying_symbol,
            prediction.exchange,
        ) != identity or (
            evidence.cycle.underlying_symbol,
            evidence.cycle.exchange,
        ) != identity:
            raise ValueError("cycle evidence identity")
        if (
            evidence.execution_mode != "PAPER"
            or evidence.broker_order_submission is not False
            or evidence.live_execution_eligible is not False
        ):
            raise ValueError("PAPER-only cycle evidence")
    return MappingProxyType(copied)


def _has_authoritative_provider_data_incident(prediction) -> bool:
    """Accept only persisted provider-failure provenance, never a WAIT alone."""

    reasons = frozenset(
        (*prediction.errors, *prediction.blockers, *prediction.rationale)
    )
    return bool(reasons & _PROVIDER_DATA_INCIDENT_REASONS)


def _recover_prediction_and_window(
    *,
    evidence: Task9CycleMarketEvidenceV1,
    prediction_ledger: PredictionLedger,
    lifecycle_context_store: Task9PredictionLifecycleContextStore,
    observation_store: Task9PredictionObservationWindowStore,
):
    prediction = prediction_ledger.recover(
        evidence.prediction.prediction_id
    )
    if prediction != evidence.prediction:
        raise ValueError("durable prediction identity")
    context = lifecycle_context_store.recover(prediction.prediction_id)
    if context is None:
        raise ValueError("durable prediction lifecycle context")
    if (
        context.prediction_id != prediction.prediction_id
        or context.parent_cycle_id != prediction.parent_cycle_id
        or context.underlying_symbol != prediction.underlying_symbol
        or context.exchange != prediction.exchange
    ):
        raise ValueError("durable prediction context identity")
    window = observation_store.recover(prediction.prediction_id)
    return prediction, context, window


def _save_or_recover_outcome(
    *,
    outcome,
    outcome_store: Task9PredictionLifecycleOutcomeStore,
):
    existing = outcome_store.recover(outcome.prediction_id)
    if existing is not None:
        if existing != outcome:
            raise ValueError("conflicting durable lifecycle outcome")
        return existing
    outcome_store.save(outcome)
    recovered = outcome_store.recover(outcome.prediction_id)
    if recovered != outcome:
        raise ValueError("durable lifecycle outcome recovery")
    return recovered


def _persist_or_recover_outcome(
    *,
    prediction,
    observation_window,
    outcome_policy: PredictionLifecycleOutcomePolicyV1,
    evaluated_at: datetime,
    outcome_store: Task9PredictionLifecycleOutcomeStore,
):
    outcome = evaluate_prediction_lifecycle_outcome(
        PredictionLifecycleOutcomeInputV1(
            prediction=prediction,
            observation_window=observation_window,
            policy=outcome_policy,
            evaluated_at=evaluated_at,
        )
    )
    return _save_or_recover_outcome(
        outcome=outcome,
        outcome_store=outcome_store,
    )


def _persist_or_recover_reconciliation(
    *,
    prediction,
    outcome,
    position,
    pnl_evidence,
    reconciled_at: datetime,
    reconciliation_store: Task9PredictionLifecycleReconciliationStore,
):
    reconciliation = reconcile_prediction_lifecycle(
        prediction=prediction,
        outcome=outcome,
        position=position,
        reconciled_at=reconciled_at,
        pnl_evidence=pnl_evidence,
    )
    existing = reconciliation_store.recover(prediction.prediction_id)
    if existing is not None:
        if existing != reconciliation:
            raise ValueError("conflicting durable lifecycle reconciliation")
        return existing
    reconciliation_store.save(reconciliation)
    recovered = reconciliation_store.recover(prediction.prediction_id)
    if recovered != reconciliation:
        raise ValueError("durable lifecycle reconciliation recovery")
    return recovered


def _validated_binding_snapshot(
    *,
    evidence: Task9CycleMarketEvidenceV1,
    official_run_id: str,
    binding_store: Task9PredictionPaperTradeBindingStore,
    trade_persistence_service: PaperTradePersistenceService,
):
    prediction = evidence.prediction
    binding = binding_store.by_prediction(prediction.prediction_id)
    if binding is None:
        return None, None
    if (
        binding.official_run_id != official_run_id
        or binding.prediction_id != prediction.prediction_id
        or binding.market != prediction.underlying_symbol
        or binding.underlying_exchange != prediction.exchange
    ):
        raise ValueError("prediction binding identity")
    snapshot = trade_persistence_service.get(binding.paper_trade_id)
    if snapshot is None:
        raise ValueError("bound PAPER snapshot unavailable")
    if (
        type(snapshot) is not PaperTradePersistenceSnapshotV1
        or snapshot.paper_trade_id != binding.paper_trade_id
        or snapshot.position is None
        or snapshot.position.position_id != binding.paper_position_id
        or snapshot.position.underlying_symbol
        != prediction.underlying_symbol
        or snapshot.position.option_symbol != binding.option_symbol
    ):
        raise ValueError("bound PAPER position identity")
    return binding, snapshot


def build_task9_production_child_authority(
    *,
    official_run_id: str,
    cycle_evidence_by_market: Mapping[
        MarketIdentity,
        Task9CycleMarketEvidenceV1,
    ],
    evaluated_at: datetime,
    prediction_ledger: PredictionLedger,
    binding_store: Task9PredictionPaperTradeBindingStore,
    trade_persistence_service: PaperTradePersistenceService,
    lifecycle_context_store: Task9PredictionLifecycleContextStore,
    observation_store: Task9PredictionObservationWindowStore,
    outcome_store: Task9PredictionLifecycleOutcomeStore,
    reconciliation_store: Task9PredictionLifecycleReconciliationStore,
    outcome_policy: PredictionLifecycleOutcomePolicyV1,
    session_policy: MarketSessionPolicy = MarketSessionPolicy(),
    entry_delegate: EntryDelegate | None = None,
    monitoring_delegate: MonitoringDelegate | None = None,
):
    """Build the runner-compatible, no-provider Task 9 child authority.

    ``entry_delegate`` must invoke the existing
    ``execute_task9_selected_market_lifecycle`` with the exact pre-built entry
    inputs.  ``monitoring_delegate`` must invoke the existing
    ``execute_task9_position_monitoring`` with the supplied exact snapshot and
    observation.  Their return values are deliberately ignored: durable stores
    remain the sole authority for the next child state.
    """

    run_id = _nonempty(official_run_id, "official_run_id")
    boundary = _aware(evaluated_at, "evaluated_at")
    handoffs = _freeze_handoffs(cycle_evidence_by_market)
    if type(prediction_ledger) is not PredictionLedger:
        raise TypeError("prediction_ledger")
    if type(binding_store) is not Task9PredictionPaperTradeBindingStore:
        raise TypeError("binding_store")
    if type(trade_persistence_service) is not PaperTradePersistenceService:
        raise TypeError("trade_persistence_service")
    if type(lifecycle_context_store) is not Task9PredictionLifecycleContextStore:
        raise TypeError("lifecycle_context_store")
    if type(observation_store) is not Task9PredictionObservationWindowStore:
        raise TypeError("observation_store")
    if type(outcome_store) is not Task9PredictionLifecycleOutcomeStore:
        raise TypeError("outcome_store")
    if type(reconciliation_store) is not Task9PredictionLifecycleReconciliationStore:
        raise TypeError("reconciliation_store")
    if type(outcome_policy) is not PredictionLifecycleOutcomePolicyV1:
        raise TypeError("outcome_policy")
    if type(session_policy) is not MarketSessionPolicy:
        raise TypeError("session_policy")
    if entry_delegate is not None and not callable(entry_delegate):
        raise TypeError("entry_delegate")
    if monitoring_delegate is not None and not callable(monitoring_delegate):
        raise TypeError("monitoring_delegate")

    def terminal_evidence(
        evidence: Task9CycleMarketEvidenceV1,
        snapshot: PaperTradePersistenceSnapshotV1,
    ) -> Task9MarketCycleEvidenceV1:
        prediction, _, window = _recover_prediction_and_window(
            evidence=evidence,
            prediction_ledger=prediction_ledger,
            lifecycle_context_store=lifecycle_context_store,
            observation_store=observation_store,
        )
        if window is None:
            raise ValueError("terminal prediction observation window")
        if not snapshot.lifecycle_state.is_terminal:
            raise ValueError("terminal evidence requires terminal P7 state")
        outcome = _persist_or_recover_outcome(
            prediction=prediction,
            observation_window=window,
            outcome_policy=outcome_policy,
            evaluated_at=boundary,
            outcome_store=outcome_store,
        )
        reconciliation = _persist_or_recover_reconciliation(
            prediction=prediction,
            outcome=outcome,
            position=snapshot.position,
            pnl_evidence=snapshot.pnl_evidence,
            reconciled_at=boundary,
            reconciliation_store=reconciliation_store,
        )
        return Task9MarketCycleEvidenceV1(
            prediction=prediction,
            lifecycle_outcome=outcome,
            reconciliation=reconciliation,
            terminal_position_closed=True,
            record_source="LIVE_REAL_TIME",
            evidence_status="VALID",
        )

    def child_authority(
        market: str,
        exchange: str,
        entry_allowed: bool,
    ) -> Task9MarketCycleEvidenceV1:
        safe_market = market if market in {"NIFTY", "SENSEX"} else "UNKNOWN"
        stage = "INPUT_HANDOFF_VALIDATION"
        try:
            identity = (market, exchange)
            if identity not in _MARKETS: raise ValueError("market identity")
            if type(entry_allowed) is not bool: raise TypeError("entry_allowed")
            evidence = handoffs[identity]
            if evidence.market_quote is not None and evidence.data_quality is not None:
                stage = "ABSTENTION_LATER_OBSERVATION_RECOVERY"
                recover_task9_later_abstention_observations(market=market, exchange=exchange, quote=evidence.market_quote, data_quality=evidence.data_quality, prediction_ledger=prediction_ledger, lifecycle_context_store=lifecycle_context_store, observation_store=observation_store, outcome_store=outcome_store, outcome_policy=outcome_policy, evaluated_at=boundary, session_policy=session_policy)
            stage = "PREDICTION_RECOVERY"
            prediction, context, _ = _recover_prediction_and_window(evidence=evidence, prediction_ledger=prediction_ledger, lifecycle_context_store=lifecycle_context_store, observation_store=observation_store)
            stage = "DATA_INCIDENT_PROJECTION"
            failed = prediction.terminal_status in {"FAILED", "UNAVAILABLE"}
            incident = prediction.terminal_status == "COMPLETED" and prediction.eligibility == "UNAVAILABLE" and prediction.predicted_action in {"WAIT", "NO_TRADE"} and _has_authoritative_provider_data_incident(prediction)
            if failed:
                if evidence.evaluation is not None: raise ValueError("failed prediction cannot retain evaluation")
                if _has_authoritative_provider_data_incident(prediction):
                    return Task9MarketCycleEvidenceV1(prediction=prediction, evidence_status="DATA_INCIDENT")
                # A generic failed child already carries its fail-closed
                # terminal prediction and sanitized diagnostic.  It is not a
                # provider incident, and must not enter any lifecycle path.
                return Task9MarketCycleEvidenceV1(prediction=prediction)
            if incident:
                if evidence.selected_planning is not None or evidence.paper_observation is not None: raise ValueError("completed provider incident cannot retain entry evidence")
                return Task9MarketCycleEvidenceV1(prediction=prediction, evidence_status="DATA_INCIDENT")
            non_entry_prediction = (
                prediction.predicted_action in _ABSTENTION_ACTIONS
                or (
                    prediction.predicted_action in _ENTRY_ACTIONS
                    and not prediction.parent_selected
                )
            )
            if non_entry_prediction:
                stage = "NON_ENTRY_OBSERVATION"
                if evidence.market_quote is None or evidence.data_quality is None: raise ValueError("abstention quote evidence")
                # Task 8's retained spot can legitimately predate parent prediction
                # completion.  It initializes durable lifecycle state but is never
                # re-labelled as a post-prediction observation.
                observation_store.initialize(prediction=prediction, entry_window_ends_at=context.entry_window_ends_at, validity_window_ends_at=context.validity_window_ends_at)
                if evidence.market_quote.observed_at < prediction.completed_at:
                    return Task9MarketCycleEvidenceV1(prediction=prediction, lifecycle_outcome=None, reconciliation=None, terminal_position_closed=False)
                record_task9_abstention_prediction_observation(prediction_id=prediction.prediction_id, quote=evidence.market_quote, data_quality=evidence.data_quality, prediction_ledger=prediction_ledger, lifecycle_context_store=lifecycle_context_store, observation_store=observation_store)
                stage = "LIFECYCLE_RECOVERY"
                _, _, window = _recover_prediction_and_window(evidence=evidence, prediction_ledger=prediction_ledger, lifecycle_context_store=lifecycle_context_store, observation_store=observation_store)
                if window is None: raise ValueError("abstention prediction observation window")
                stage = "OUTCOME_RECOVERY"
                candidate = evaluate_prediction_lifecycle_outcome(PredictionLifecycleOutcomeInputV1(prediction=prediction, observation_window=window, policy=outcome_policy, evaluated_at=boundary))
                outcome = None if candidate.evaluation_status == "UNRESOLVED" else _save_or_recover_outcome(outcome=candidate, outcome_store=outcome_store)
                return Task9MarketCycleEvidenceV1(prediction=prediction, lifecycle_outcome=outcome, reconciliation=None, terminal_position_closed=False)
            stage = "PREDICTION_VALIDATION"
            if prediction.predicted_action not in _ENTRY_ACTIONS:
                raise ValueError("unsupported prediction action")
            if not prediction.parent_selected:
                raise ValueError(
                    "directional entry requires parent-selected prediction"
                )
            stage = "ENTRY_BINDING"
            binding, snapshot = _validated_binding_snapshot(evidence=evidence, official_run_id=run_id, binding_store=binding_store, trade_persistence_service=trade_persistence_service)
            if binding is None:
                if not entry_allowed: return Task9MarketCycleEvidenceV1(prediction=prediction)
                if entry_delegate is None: raise ValueError("entry_delegate is required")
                stage = "ENTRY_DELEGATE"; entry_delegate(evidence, prediction.prediction_id)
                stage = "ENTRY_BINDING"; binding, snapshot = _validated_binding_snapshot(evidence=evidence, official_run_id=run_id, binding_store=binding_store, trade_persistence_service=trade_persistence_service)
                if binding is None: return Task9MarketCycleEvidenceV1(prediction=prediction)
                assert snapshot is not None
                if snapshot.lifecycle_state.is_terminal:
                    stage = "TERMINAL_LIFECYCLE_RECOVERY"; return terminal_evidence(evidence, snapshot)
                return Task9MarketCycleEvidenceV1(prediction=prediction)
            assert snapshot is not None
            if snapshot.lifecycle_state.is_terminal:
                stage = "TERMINAL_LIFECYCLE_RECOVERY"; return terminal_evidence(evidence, snapshot)
            stage = "MONITORING_VALIDATION"
            observation = evidence.paper_observation
            if observation is None: raise ValueError("active binding requires paper observation")
            if observation.underlying_symbol != prediction.underlying_symbol or observation.market != prediction.underlying_symbol or observation.option_symbol != binding.option_symbol: raise ValueError("monitoring observation identity")
            if monitoring_delegate is None: raise ValueError("monitoring_delegate is required")
            stage = "MONITORING_DELEGATE"; monitoring_delegate(evidence, snapshot, observation)
            stage = "ENTRY_BINDING"; _, monitored_snapshot = _validated_binding_snapshot(evidence=evidence, official_run_id=run_id, binding_store=binding_store, trade_persistence_service=trade_persistence_service)
            assert monitored_snapshot is not None
            if not monitored_snapshot.lifecycle_state.is_terminal: return Task9MarketCycleEvidenceV1(prediction=prediction)
            stage = "TERMINAL_LIFECYCLE_RECOVERY"; return terminal_evidence(evidence, monitored_snapshot)
        except Exception as exc:
            logger.error("TASK9_CHILD_AUTHORITY_FAILURE market=%s stage=%s error_type=%s", safe_market, stage, type(exc).__name__)
            raise

    return child_authority
