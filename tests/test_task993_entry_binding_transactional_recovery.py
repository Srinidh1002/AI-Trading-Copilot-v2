"""Task 9.93 crash-window coverage for durable P7-to-P8 recovery."""
import json
from dataclasses import replace

import pytest

from services.certification.task9_pending_entry_store import (
    Task9PendingEntryStore,
    Task9PendingEntryV1,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    continue_task9_pending_entry,
)
from services.contracts.paper_trade_lifecycle_state_v1 import (
    PaperTradeLifecycleStateV1,
)
from services.contracts.entry_zone_evaluation_result_v1 import EntryZoneEvaluationResultV1
from services.contracts.stop_loss_evaluation_result_v1 import StopLossEvaluationResultV1
from services.contracts.three_target_evaluation_result_v1 import ThreeTargetEvaluationResultV1
from services.contracts.option_contract_selection_result_v1 import OptionContractSelectionResultV1
from services.contracts.capital_quantity_planning_result_v1 import CapitalQuantityPlanningResultV1
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleInputV1,
)
from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
    execute_admitted_plan_simulated_entry,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)


def _pending(entry):
    return Task9PendingEntryV1(
        prediction_id=entry.prediction_id,
        parent_cycle_id="task993-parent",
        market=entry.observation.market,
        option_symbol=entry.observation.option_symbol,
        input_value=entry,
        lifecycle_state=PaperTradeLifecycleStateV1(
            lifecycle_state_id="task993-waiting",
            trade_plan_id=entry.integrated_trade_plan_result.capital_quantity_result.trade_plan_id,
            integrated_trade_plan_result_id=entry.integrated_trade_plan_result.integration_id,
            lifecycle_policy_id=entry.lifecycle_policy.lifecycle_policy_id,
            current_state="WAITING_FOR_ENTRY",
            lifecycle_created_at=entry.evaluated_at,
            previous_state="PLANNED",
            transition_sequence=1,
            last_observation_id=entry.observation.observation_id,
            last_observation_timestamp=entry.observation.observed_at,
            waiting_for_entry_at=entry.evaluated_at,
            decision_reasons=("WAITING_FOR_ENTRY_ZONE",),
        ),
    )


def _serializable_entry(args, prediction_id):
    """Reuse R4.2's exact typed, JSON-serializable P6/P8 fixture."""
    admission = args["admission_result"]
    names = (
        "portfolio_id",
        "paper_trade_id", "paper_trade_adapter_idempotency_key",
        "initial_lifecycle_state_id", "resulting_lifecycle_state_id",
        "requested_transition_id", "position_id", "entry_fill_id",
        "activation_result_snapshot_id", "activation_portfolio_event_id",
        "activation_update_idempotency_key",
        "evaluated_at", "integrated_trade_plan_result", "portfolio_policy",
        "lifecycle_policy", "observation",
    )
    values = {
        **{name: args[name] for name in names},
        "initial_portfolio_snapshot_id": "r42-initial",
        "admission_result_id": admission.admission_result_id,
        "admission_request_id": admission.admission_request_id,
        "admission_idempotency_key": admission.admission_idempotency_key,
        "admission_portfolio_event_id": admission.portfolio_event_id,
        "requested_reservation_id": admission.requested_reservation_id,
        "trading_day_id": admission.trading_day_id,
        "starting_capital": admission.resulting_snapshot.starting_capital,
    }
    return NewEntryPaperLifecycleInputV1(
        **values,
        prediction_id=prediction_id,
    )


def _crashed_after_p7(tmp_path, monkeypatch):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(args, "task993-prediction")
    original = PaperPortfolioLifecycleCoordinator.apply_p7_snapshot
    monkeypatch.setattr(
        PaperPortfolioLifecycleCoordinator,
        "apply_p7_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("crash after P7")),
    )
    with pytest.raises(RuntimeError, match="crash after P7"):
        execute_admitted_plan_simulated_entry(**args)
    monkeypatch.setattr(PaperPortfolioLifecycleCoordinator, "apply_p7_snapshot", original)
    assert trades.get(entry.paper_trade_id).lifecycle_state.current_state == "OPEN"
    assert portfolios.get(entry.portfolio_id).portfolio_snapshot.reservations[0].reservation_status == "PENDING_HOLD"
    return entry, portfolios, trades


def test_recovered_open_p7_activates_pending_p8_before_binding_and_is_idempotent(tmp_path, monkeypatch):
    entry, portfolios, trades = _crashed_after_p7(tmp_path, monkeypatch)
    pending_store = Task9PendingEntryStore(tmp_path / "pending.json")
    binding_store = Task9PredictionPaperTradeBindingStore(tmp_path / "bindings.json")
    pending = _pending(entry)
    assert pending_store.save(pending) == "SAVED"
    assert pending_store.recover(entry.prediction_id) == pending
    recovered_input = pending_store.recover(entry.prediction_id).input_value
    recovered_plan = recovered_input.integrated_trade_plan_result
    assert type(recovered_plan.entry_zone_result) is EntryZoneEvaluationResultV1
    assert type(recovered_plan.stop_loss_result) is StopLossEvaluationResultV1
    assert type(recovered_plan.three_target_result) is ThreeTargetEvaluationResultV1
    assert type(recovered_plan.option_contract_selection_result) is OptionContractSelectionResultV1
    assert type(recovered_plan.capital_quantity_result) is CapitalQuantityPlanningResultV1
    assert pending_store.save(pending_store.recover(entry.prediction_id)) == "DUPLICATE_SAME_PAYLOAD"

    first = continue_task9_pending_entry(
        official_run_id="task993-run", prediction_id=entry.prediction_id,
        observation=entry.observation, evaluated_at=entry.evaluated_at,
        pending_entry_store=pending_store, trade_persistence_service=trades,
        portfolio_persistence_service=portfolios, binding_store=binding_store,
    )
    p8_after_first = portfolios.get(entry.portfolio_id)
    second = continue_task9_pending_entry(
        official_run_id="task993-run", prediction_id=entry.prediction_id,
        observation=entry.observation, evaluated_at=entry.evaluated_at,
        pending_entry_store=pending_store, trade_persistence_service=trades,
        portfolio_persistence_service=portfolios, binding_store=binding_store,
    )

    assert first.status == second.status == "OPEN"
    assert p8_after_first.portfolio_snapshot.reservations[0].reservation_status == "ACTIVE"
    assert portfolios.get(entry.portfolio_id) == p8_after_first
    assert len(p8_after_first.portfolio_snapshot.position_references) == 1
    assert binding_store.by_prediction(entry.prediction_id).paper_trade_id == entry.paper_trade_id
    assert binding_store.by_prediction(entry.prediction_id).execution_mode == "PAPER"
    assert binding_store.by_prediction(entry.prediction_id).live_execution_eligible is False


def test_active_p8_missing_binding_repairs_only_binding_and_pending_state(tmp_path):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(args, "task993-active")
    execute_admitted_plan_simulated_entry(**args)
    before = portfolios.get(entry.portfolio_id)
    pending_store = Task9PendingEntryStore(tmp_path / "pending.json")
    binding_store = Task9PredictionPaperTradeBindingStore(tmp_path / "bindings.json")
    pending = _pending(entry)
    assert pending_store.save(pending) == "SAVED"
    assert pending_store.recover(entry.prediction_id) == pending

    result = continue_task9_pending_entry(
        official_run_id="task993-run", prediction_id=entry.prediction_id,
        observation=entry.observation, evaluated_at=entry.evaluated_at,
        pending_entry_store=pending_store, trade_persistence_service=trades,
        portfolio_persistence_service=portfolios, binding_store=binding_store,
    )

    assert result.status == "OPEN"
    assert portfolios.get(entry.portfolio_id) == before
    assert binding_store.by_prediction(entry.prediction_id).paper_position_id == entry.position_id


def test_malformed_nested_pending_plan_fails_closed(tmp_path):
    args, _, _ = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(args, "task993-malformed")
    store = Task9PendingEntryStore(tmp_path / "pending.json")
    store.save(_pending(entry))
    document = store._read()
    del document["entries"][entry.prediction_id]["input"]["integrated_trade_plan_result"]["entry_zone_result"]["status"]
    store.file_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises((KeyError, TypeError, ValueError)):
        store.recover(entry.prediction_id)
