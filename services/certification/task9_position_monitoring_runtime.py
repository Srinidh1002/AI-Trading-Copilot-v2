"""Task 9 wrapper around the existing persisted P7/P8 monitor; no market reads."""
from __future__ import annotations
from dataclasses import dataclass

from services.certification.task9_prediction_lifecycle_context_store import Task9PredictionLifecycleContextStore
from services.certification.task9_prediction_observation_projection import project_task9_prediction_observation
from services.certification.task9_prediction_observation_recorder import Task9PredictionObservationRecorder
from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore
from services.contracts.paper_market_observation_v1 import PaperMarketObservationV1
from services.contracts.paper_trade_persistence_snapshot_v1 import PaperTradePersistenceSnapshotV1
from services.contracts.task9_prediction_paper_market_identity_v1 import build_task9_prediction_paper_market_identity
from services.paper_orchestration.prediction_ledger import PredictionLedger

@dataclass(frozen=True, slots=True)
class Task9PositionMonitoringResultV1:
    paper_trade_id: str; prediction_id: str; monitoring_status: str; newly_persisted_fill_reasons: tuple[str, ...]; recorded_observation_ids: tuple[str, ...]
    execution_mode: str = "PAPER"; live_execution_eligible: bool = False; broker_order_submission: bool = False
    def __post_init__(self):
        if not all(isinstance(x, str) and x for x in (self.paper_trade_id, self.prediction_id, self.monitoring_status)) or self.execution_mode != "PAPER" or self.live_execution_eligible or self.broker_order_submission: raise ValueError("Task 9 monitoring result")

def execute_task9_position_monitoring(*, recovered_snapshot: PaperTradePersistenceSnapshotV1, observation: PaperMarketObservationV1, prediction_ledger: PredictionLedger, binding_store: Task9PredictionPaperTradeBindingStore, lifecycle_context_store: Task9PredictionLifecycleContextStore, observation_store: Task9PredictionObservationWindowStore, monitor, monitor_kwargs: dict) -> Task9PositionMonitoringResultV1:
    if type(recovered_snapshot) is not PaperTradePersistenceSnapshotV1 or type(observation) is not PaperMarketObservationV1 or type(prediction_ledger) is not PredictionLedger or type(binding_store) is not Task9PredictionPaperTradeBindingStore or type(lifecycle_context_store) is not Task9PredictionLifecycleContextStore or type(observation_store) is not Task9PredictionObservationWindowStore or not callable(monitor) or type(monitor_kwargs) is not dict: raise TypeError("Task 9 monitoring inputs")
    binding = binding_store.by_trade(recovered_snapshot.paper_trade_id)
    if binding is None: raise ValueError("Task 9 binding unavailable")
    prediction = prediction_ledger.recover(binding.prediction_id)
    context = lifecycle_context_store.recover(binding.prediction_id)
    if prediction is None or context is None: raise ValueError("Task 9 prediction context unavailable")
    bridge = build_task9_prediction_paper_market_identity(prediction=prediction, binding=binding)
    if recovered_snapshot.position is None or recovered_snapshot.position.option_symbol != binding.option_symbol or observation.option_symbol != binding.option_symbol: raise ValueError("Task 9 option identity mismatch")
    if monitor_kwargs.get("observation") is not observation:
        raise ValueError("Task 9 monitor must receive the exact supplied observation")
    observation_store.initialize(prediction=prediction, entry_window_ends_at=context.entry_window_ends_at, validity_window_ends_at=context.validity_window_ends_at)
    before = {fill.fill_id for fill in (recovered_snapshot.position.entry_fill, *recovered_snapshot.position.exit_fills)}
    result = monitor(**monitor_kwargs)
    after = result.p7_snapshot
    if after.position is None: raise ValueError("Task 9 monitor missing persisted position")
    fills = tuple(fill for fill in (after.position.entry_fill, *after.position.exit_fills) if fill.fill_id not in before)
    recorder = Task9PredictionObservationRecorder(observation_store); recorded=[]
    terminal_fill = after.position.exit_fills[-1] if after.lifecycle_state.is_terminal and after.position.exit_fills else None
    for fill in fills or (None,):
        terminal_event = None
        if fill is terminal_fill and fill.fill_reason in {"TARGET_1", "TARGET_2", "TARGET_3"}:
            expected = f"CLOSED_{fill.fill_reason}"
            if after.position.lifecycle_state != expected or after.position.remaining_quantity != 0 or fill.position_id != after.position.position_id or fill.selected_option_contract_id != after.position.selected_option_contract_id:
                raise ValueError("terminal P7 target evidence mismatch")
            terminal_event = f"TERMINAL_{fill.fill_reason.replace('TARGET_', 'T')}"
        event = "NONE" if fill is None and observation.data_quality_status == "FRESH" else "DATA_GAP" if fill is None else terminal_event or {"ENTRY_ACTIVATED":"ENTRY","TARGET_1":"T1","TARGET_2":"T2","TARGET_3":"T3","STOP":"STOP","RUNNER_CLOSE":"EARLY_EXIT","INVALIDATED":"INVALIDATED","SESSION_CLOSE":"SESSION_CLOSE","EXPIRY_CLOSE":"EXPIRY","CANCELLED":"EARLY_EXIT"}.get(fill.fill_reason)
        if event is None: continue
        item = recorder.record_projected(prediction_id=prediction.prediction_id, source_observation_id=observation.observation_id, event_type=event, factory=lambda sequence, fill=fill, terminal_event=terminal_event: project_task9_prediction_observation(prediction=prediction, bridge=bridge, lifecycle_context=context, paper_observation=observation, lifecycle_fill=fill, terminal_event_type=terminal_event, sequence_number=sequence))
        recorded.append(item.observation_id)
    return Task9PositionMonitoringResultV1(recovered_snapshot.paper_trade_id, prediction.prediction_id, result.status, tuple(fill.fill_reason for fill in fills), tuple(recorded))
