"""Task 9 binding installation for the existing selected PAPER lifecycle."""

from __future__ import annotations

from services.certification.task9_selected_market_lifecycle_runtime import (
    execute_task9_selected_market_lifecycle as execute_task9_selected_market_lifecycle_runtime,
)
from services.certification.task9_paper_portfolio_policy_store import (
    Task9PaperPortfolioPolicyStore,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_observation_projection import (
    project_task9_prediction_observation,
)
from services.certification.task9_prediction_observation_recorder import (
    Task9PredictionObservationRecorder,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
    Task9PredictionPaperTradeBindingV1,
)
from services.certification.task9_pending_entry_store import (
    Task9PendingEntryStore,
    Task9PendingEntryV1,
)
from services.contracts.paper_trade_entry_evaluation_input_v1 import PaperTradeEntryEvaluationInputV1
from services.contracts.paper_market_observation_v1 import PaperMarketObservationV1
from services.paper_orchestration.paper_state_factories import build_entry_paper_trade_persistence_snapshot
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import PaperPortfolioLifecycleCoordinator
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_trading.paper_trade_entry_evaluator import evaluate_paper_trade_entry
from services.paper_trading.paper_trade_persistence_service import PaperTradePersistenceService
from services.contracts.task9_prediction_paper_market_identity_v1 import (
    build_task9_prediction_paper_market_identity,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleInputV1,
    NewEntryPaperLifecycleResultV1,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)


def build_task9_binding_persistor(
    *,
    official_run_id: str,
    store: Task9PredictionPaperTradeBindingStore,
):
    if (
        type(official_run_id) is not str
        or not official_run_id.strip()
    ):
        raise ValueError("official_run_id")

    if type(store) is not Task9PredictionPaperTradeBindingStore:
        raise TypeError("store")

    def persist(
        input_value,
        result,
    ) -> None:
        if (
            type(input_value)
            is not NewEntryPaperLifecycleInputV1
            or type(result)
            is not NewEntryPaperLifecycleResultV1
        ):
            raise TypeError(
                "Task 9 binding callback contract"
            )

        if (
            result.status != "OPEN"
            or result.p7_snapshot is None
            or input_value.prediction_id is None
        ):
            raise ValueError(
                "Task 9 binding requires successful "
                "identified PAPER entry"
            )

        position = result.p7_snapshot.position

        if position is None:
            raise ValueError(
                "OPEN P7 snapshot missing position"
            )

        store.save(
            Task9PredictionPaperTradeBindingV1(
                official_run_id=official_run_id,
                prediction_id=input_value.prediction_id,
                market=position.underlying_symbol,
                paper_trade_id=(
                    result.p7_snapshot.paper_trade_id
                ),
                paper_position_id=position.position_id,
                option_symbol=position.option_symbol,
                entered_at=position.opened_at,
            )
        )

    return persist


def execute_task9_selected_market_lifecycle(
    *,
    official_run_id: str,
    binding_store: Task9PredictionPaperTradeBindingStore,
    prediction_id: str,
    prediction_ledger: PredictionLedger | None = None,
    lifecycle_context_store: (
        Task9PredictionLifecycleContextStore | None
    ) = None,
    observation_store: (
        Task9PredictionObservationWindowStore | None
    ) = None,
    portfolio_policy_store: (
        Task9PaperPortfolioPolicyStore | None
    ) = None,
    pending_entry_store: Task9PendingEntryStore | None = None,
    **kwargs,
):
    if (
        type(prediction_id) is not str
        or not prediction_id.strip()
    ):
        raise ValueError(
            "Task 9 prediction_id is required"
        )

    if (
        (prediction_ledger is None)
        != (lifecycle_context_store is None)
        or (prediction_ledger is None)
        != (observation_store is None)
    ):
        raise ValueError(
            "Task 9 entry observation dependencies "
            "must be supplied together"
        )

    if prediction_ledger is not None:
        if (
            type(prediction_ledger) is not PredictionLedger
            or type(lifecycle_context_store)
            is not Task9PredictionLifecycleContextStore
            or type(observation_store)
            is not Task9PredictionObservationWindowStore
        ):
            raise TypeError(
                "Task 9 entry observation dependencies"
            )

    if (
        portfolio_policy_store is not None
        and type(portfolio_policy_store)
        is not Task9PaperPortfolioPolicyStore
    ):
        raise TypeError(
            "Task 9 portfolio policy store"
        )
    if pending_entry_store is not None and type(pending_entry_store) is not Task9PendingEntryStore:
        raise TypeError("Task 9 pending-entry store")

    binding_persistor = build_task9_binding_persistor(
        official_run_id=official_run_id,
        store=binding_store,
    )

    def persist(
        input_value,
        result,
    ):
        binding_persistor(
            input_value,
            result,
        )

        if portfolio_policy_store is not None:
            portfolio_policy_store.save(
                input_value.portfolio_policy
            )

        if prediction_ledger is None:
            return

        binding = binding_store.by_trade(
            result.p7_snapshot.paper_trade_id
        )

        if binding is None:
            raise ValueError(
                "Task 9 entry binding unavailable"
            )

        prediction = prediction_ledger.recover(
            binding.prediction_id
        )

        context = lifecycle_context_store.recover(
            binding.prediction_id
        )

        if prediction is None or context is None:
            raise ValueError(
                "Task 9 entry prediction context unavailable"
            )

        bridge = (
            build_task9_prediction_paper_market_identity(
                prediction=prediction,
                binding=binding,
            )
        )

        observation_store.initialize(
            prediction=prediction,
            entry_window_ends_at=(
                context.entry_window_ends_at
            ),
            validity_window_ends_at=(
                context.validity_window_ends_at
            ),
        )

        position = result.p7_snapshot.position

        if position is None:
            raise ValueError(
                "Task 9 OPEN snapshot missing position"
            )

        fill = position.entry_fill

        if fill is None:
            raise ValueError(
                "Task 9 OPEN snapshot missing entry fill"
            )

        observation = input_value.observation

        Task9PredictionObservationRecorder(
            observation_store
        ).record_projected(
            prediction_id=prediction.prediction_id,
            source_observation_id=(
                observation.observation_id
            ),
            event_type="ENTRY",
            factory=lambda sequence: (
                project_task9_prediction_observation(
                    prediction=prediction,
                    bridge=bridge,
                    lifecycle_context=context,
                    paper_observation=observation,
                    lifecycle_fill=fill,
                    sequence_number=sequence,
                )
            ),
        )

    return execute_task9_selected_market_lifecycle_runtime(
        prediction_id=prediction_id,
        task9_pending_entry_persistor=(
            None if pending_entry_store is None else lambda input_value, result: pending_entry_store.save(
                Task9PendingEntryV1(
                    prediction_id=prediction_id,
                    parent_cycle_id=kwargs["selected_cycle"].cycle_id,
                    market=input_value.observation.market,
                    option_symbol=input_value.observation.option_symbol,
                    input_value=input_value,
                    lifecycle_state=PaperTradeLifecycleStateV1(
                        lifecycle_state_id=input_value.resulting_lifecycle_state_id,
                        trade_plan_id=input_value.integrated_trade_plan_result.capital_quantity_result.trade_plan_id,
                        integrated_trade_plan_result_id=input_value.integrated_trade_plan_result.integration_id,
                        lifecycle_policy_id=input_value.lifecycle_policy.lifecycle_policy_id,
                        current_state="WAITING_FOR_ENTRY",
                        lifecycle_created_at=input_value.evaluated_at,
                        previous_state="PLANNED",
                        transition_sequence=1,
                        last_transition_code=input_value.requested_transition_id,
                        last_observation_id=input_value.observation.observation_id,
                        last_observation_timestamp=input_value.observation.observed_at,
                        waiting_for_entry_at=input_value.evaluated_at,
                        decision_reasons=result.entry_result.decision_reasons,
                        warnings=result.entry_result.warnings,
                    ),
                )
            )
        ),
        task9_binding_persistor=persist,
        **kwargs,
    )


def _reconcile_recovered_open_p7_portfolio(*, pending, p7_snapshot, portfolio_persistence_service, updated_at):
    """Repair only the durable P8 projection of an already durable OPEN P7."""
    if type(portfolio_persistence_service) is not PaperPortfolioPersistenceService:
        raise TypeError("portfolio_persistence_service")
    position = p7_snapshot.position
    if position is None or p7_snapshot.lifecycle_state.current_state != "OPEN":
        raise ValueError("unexpected durable pending P7 state")
    value = pending.input_value
    current = portfolio_persistence_service.get(value.portfolio_id)
    if current is None:
        raise ValueError("recovered P7 portfolio missing")
    if current.execution_mode != "PAPER" or current.live_execution_eligible is not False:
        raise ValueError("recovered P8 is not PAPER-only")

    reservations = [
        item for item in current.portfolio_snapshot.reservations
        if (
            item.reservation_id == value.requested_reservation_id
            and item.portfolio_id == value.portfolio_id
            and item.admission_request_id == value.admission_request_id
            and item.admission_idempotency_key == value.admission_idempotency_key
            and item.trade_plan_id == position.trade_plan_id
            and item.integrated_trade_plan_result_id == position.integrated_trade_plan_result_id
        )
    ]
    plan_reservations = [
        item for item in current.portfolio_snapshot.reservations
        if (
            item.trade_plan_id == position.trade_plan_id
            and item.integrated_trade_plan_result_id == position.integrated_trade_plan_result_id
        )
    ]
    if len(reservations) != 1 or len(plan_reservations) != 1:
        raise ValueError("recovered P8 matching reservation is ambiguous or missing")
    reservation = reservations[0]
    if reservation.initial_quantity != position.initial_quantity:
        raise ValueError("recovered P7/P8 reservation quantity mismatch")

    references = current.portfolio_snapshot.position_references
    related_references = [
        item for item in references
        if item.reservation_id == reservation.reservation_id or item.position_id == position.position_id
    ]
    if reservation.reservation_status == "ACTIVE":
        if (
            reservation.position_id != position.position_id
            or reservation.last_p7_lifecycle_state != "OPEN"
            or reservation.last_p7_transition_sequence != p7_snapshot.event_sequence
            or len(related_references) != 1
        ):
            raise ValueError("recovered P8 ACTIVE projection conflicts with P7")
        reference = related_references[0]
        if (
            reference.reservation_id != reservation.reservation_id
            or reference.position_id != position.position_id
            or reference.trade_plan_id != position.trade_plan_id
            or reference.integrated_trade_plan_result_id != position.integrated_trade_plan_result_id
            or reference.selected_option_contract_id != position.selected_option_contract_id
            or reference.lifecycle_state != "OPEN"
            or reference.transition_sequence != p7_snapshot.event_sequence
        ):
            raise ValueError("recovered P8 position projection conflicts with P7")
        return current
    if reservation.reservation_status != "PENDING_HOLD" or related_references:
        raise ValueError("recovered P8 reservation is not an unprojected pending hold")

    repaired = PaperPortfolioLifecycleCoordinator(
        portfolio_persistence_service
    ).apply_p7_snapshot(
        portfolio_id=value.portfolio_id,
        policy=value.portfolio_policy,
        p7_snapshot=p7_snapshot,
        result_snapshot_id=value.activation_result_snapshot_id,
        portfolio_event_id=value.activation_portfolio_event_id,
        update_idempotency_key=value.activation_update_idempotency_key,
        updated_at=updated_at,
    )
    repaired_reservations = [
        item for item in repaired.portfolio_snapshot.reservations
        if item.reservation_id == reservation.reservation_id
    ]
    repaired_references = [
        item for item in repaired.portfolio_snapshot.position_references
        if item.reservation_id == reservation.reservation_id
    ]
    if (
        len(repaired_reservations) != 1
        or len(repaired_references) != 1
        or repaired_reservations[0].reservation_status != "ACTIVE"
        or repaired_reservations[0].position_id != position.position_id
        or repaired_references[0].position_id != position.position_id
    ):
        raise ValueError("recovered P8 activation verification failed")
    return repaired


def continue_task9_pending_entry(*, official_run_id: str, prediction_id: str, observation: PaperMarketObservationV1, evaluated_at, pending_entry_store: Task9PendingEntryStore, trade_persistence_service: PaperTradePersistenceService, portfolio_persistence_service, binding_store: Task9PredictionPaperTradeBindingStore):
    """Evaluate only a recovered Task 9 pending entry; no P6/P8 admission rerun."""
    if type(observation) is not PaperMarketObservationV1 or type(pending_entry_store) is not Task9PendingEntryStore or type(trade_persistence_service) is not PaperTradePersistenceService: raise TypeError("pending continuation inputs")
    pending = pending_entry_store.recover(prediction_id)
    if pending is None: return None
    if pending.status != "WAITING_FOR_ENTRY": return pending
    value = pending.input_value
    existing_snapshot = trade_persistence_service.get(value.paper_trade_id)
    if existing_snapshot is not None:
        _reconcile_recovered_open_p7_portfolio(
            pending=pending,
            p7_snapshot=existing_snapshot,
            portfolio_persistence_service=portfolio_persistence_service,
            updated_at=evaluated_at,
        )
        if existing_snapshot.position is None or existing_snapshot.lifecycle_state.current_state != "OPEN": raise ValueError("unexpected durable pending P7 state")
        position = existing_snapshot.position
        binding_store.save(Task9PredictionPaperTradeBindingV1(official_run_id=official_run_id, prediction_id=prediction_id, market=position.underlying_symbol, paper_trade_id=existing_snapshot.paper_trade_id, paper_position_id=position.position_id, option_symbol=position.option_symbol, entered_at=position.opened_at))
        recovered = Task9PendingEntryV1(prediction_id=pending.prediction_id, parent_cycle_id=pending.parent_cycle_id, market=pending.market, option_symbol=pending.option_symbol, input_value=value, lifecycle_state=existing_snapshot.lifecycle_state, status="OPEN")
        pending_entry_store.save(recovered)
        return recovered
    if (observation.market, observation.option_symbol, observation.trade_plan_id, observation.integrated_trade_plan_result_id, observation.selected_option_contract_id) != (pending.market, pending.option_symbol, value.integrated_trade_plan_result.capital_quantity_result.trade_plan_id, value.integrated_trade_plan_result.integration_id, value.observation.selected_option_contract_id): raise ValueError("pending observation identity")
    entry_input = PaperTradeEntryEvaluationInputV1(integrated_trade_plan_result=value.integrated_trade_plan_result, lifecycle_policy=value.lifecycle_policy, lifecycle_state=pending.lifecycle_state, observation=observation, evaluation_timestamp=evaluated_at, requested_transition_id=f"{value.requested_transition_id}:continue:{observation.observation_id}", position_id=value.position_id, entry_fill_id=value.entry_fill_id)
    result = evaluate_paper_trade_entry(entry_input)
    snapshot = build_entry_paper_trade_persistence_snapshot(paper_trade_id=value.paper_trade_id, adapter_idempotency_key=value.paper_trade_adapter_idempotency_key, entry_input=entry_input, entry_result=result, resulting_lifecycle_state_id=f"{value.resulting_lifecycle_state_id}:continue:{observation.observation_id}", persisted_at=evaluated_at)
    updated = Task9PendingEntryV1(prediction_id=pending.prediction_id, parent_cycle_id=pending.parent_cycle_id, market=pending.market, option_symbol=pending.option_symbol, input_value=value, lifecycle_state=snapshot.lifecycle_state, status=result.status)
    if result.status == "OPEN":
        trade_persistence_service.save(snapshot)
        PaperPortfolioLifecycleCoordinator(portfolio_persistence_service).apply_p7_snapshot(portfolio_id=value.portfolio_id, policy=value.portfolio_policy, p7_snapshot=snapshot, result_snapshot_id=value.activation_result_snapshot_id, portfolio_event_id=value.activation_portfolio_event_id, update_idempotency_key=value.activation_update_idempotency_key, updated_at=evaluated_at)
        position = snapshot.position
        if position is None: raise ValueError("pending OPEN snapshot missing position")
        binding_store.save(Task9PredictionPaperTradeBindingV1(official_run_id=official_run_id, prediction_id=prediction_id, market=position.underlying_symbol, paper_trade_id=snapshot.paper_trade_id, paper_position_id=position.position_id, option_symbol=position.option_symbol, entered_at=position.opened_at))
    pending_entry_store.save(updated)
    return updated
