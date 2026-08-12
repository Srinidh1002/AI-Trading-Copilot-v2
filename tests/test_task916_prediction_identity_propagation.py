import inspect
from dataclasses import replace

from services.paper_orchestration.authoritative_two_market_entry_point import (
    run_authoritative_two_market_parent_cycle,
)
from services.paper_orchestration.new_entry_paper_lifecycle_executor import (
    NewEntryPaperLifecycleInputV1,
)
from services.certification.task8_selected_market_lifecycle_runtime import (
    execute_task8_selected_market_lifecycle,
)
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore
from services.certification.task9_selected_market_lifecycle_composition import build_task9_binding_persistor
from services.certification.task9_pending_entry_store import Task9PendingEntryStore, Task9PendingEntryV1
from services.contracts.paper_trade_lifecycle_state_v1 import PaperTradeLifecycleStateV1
from services.paper_orchestration.new_entry_paper_lifecycle_executor import NewEntryPaperLifecycleExecutor
from tests.test_apt2_paper_lifecycle_certification import _entry_input, _services


def test_authoritative_prediction_identity_has_additive_entry_propagation_hooks():
    assert "prediction_records_sink" in inspect.signature(
        run_authoritative_two_market_parent_cycle
    ).parameters
    assert "prediction_id" in NewEntryPaperLifecycleInputV1.__dataclass_fields__
    parameters = inspect.signature(
        execute_task8_selected_market_lifecycle
    ).parameters
    assert "prediction_id" in parameters
    assert "task9_binding_persistor" in parameters
    assert "task9_pending_entry_persistor" in parameters


def test_pending_entry_authority_is_json_restart_recoverable(tmp_path):
    entry = replace(_entry_input(), prediction_id="prediction-pending-1")
    state = PaperTradeLifecycleStateV1(
        lifecycle_state_id="pending-state",
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
    )
    pending = Task9PendingEntryV1(
        prediction_id=entry.prediction_id,
        parent_cycle_id="parent-cycle-pending-1",
        market=entry.observation.market,
        option_symbol=entry.observation.option_symbol,
        input_value=entry,
        lifecycle_state=state,
    )
    path = tmp_path / "pending.json"
    assert Task9PendingEntryStore(path).save(pending) == "SAVED"
    recovered = Task9PendingEntryStore(path).recover(entry.prediction_id)
    assert recovered.lifecycle_state.current_state == "WAITING_FOR_ENTRY"
    assert recovered.input_value.integrated_trade_plan_result.integration_id == entry.integrated_trade_plan_result.integration_id


def test_successful_real_p7_entry_persists_restart_recoverable_binding(tmp_path):
    portfolios, trades = _services(tmp_path)
    entry = replace(_entry_input(), prediction_id="prediction-authoritative-1")
    result = NewEntryPaperLifecycleExecutor(
        portfolio_persistence_service=portfolios,
        trade_persistence_service=trades,
    ).execute(entry)
    store_path = tmp_path / "task9-bindings.json"
    build_task9_binding_persistor(
        official_run_id="task9-run-1",
        store=Task9PredictionPaperTradeBindingStore(store_path),
    )(entry, result)
    recovered = Task9PredictionPaperTradeBindingStore(store_path).by_trade(
        result.p7_snapshot.paper_trade_id
    )
    assert recovered.prediction_id == "prediction-authoritative-1"
    assert recovered.paper_position_id == result.p7_snapshot.position.position_id
