"""Pure Task 9 projection of persisted PAPER evidence."""
from __future__ import annotations

from services.contracts.paper_market_observation_v1 import PaperMarketObservationV1
from services.contracts.paper_trade_fill_v1 import PaperTradeFillV1
from services.contracts.prediction_lifecycle_timing_v1 import PredictionLifecycleWindowV1
from services.contracts.prediction_observation_v1 import PredictionObservationV1
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.contracts.task9_prediction_paper_market_identity_v1 import Task9PredictionPaperMarketIdentityV1

_EVENTS = {"ENTRY_ACTIVATED": "ENTRY", "TARGET_1": "T1", "TARGET_2": "T2", "TARGET_3": "T3", "STOP": "STOP", "RUNNER_CLOSE": "EARLY_EXIT"}

def project_task9_prediction_observation(*, prediction: PredictionRecordV1, bridge: Task9PredictionPaperMarketIdentityV1, lifecycle_context: PredictionLifecycleWindowV1, paper_observation: PaperMarketObservationV1, sequence_number: int, lifecycle_fill: PaperTradeFillV1 | None = None, terminal_event_type: str | None = None) -> PredictionObservationV1:
    if type(prediction) is not PredictionRecordV1 or type(bridge) is not Task9PredictionPaperMarketIdentityV1 or type(lifecycle_context) is not PredictionLifecycleWindowV1 or type(paper_observation) is not PaperMarketObservationV1:
        raise TypeError("projection inputs")
    if type(sequence_number) is not int or isinstance(sequence_number, bool) or sequence_number <= 0: raise ValueError("sequence_number")
    if (prediction.prediction_id, prediction.parent_cycle_id, prediction.underlying_symbol, prediction.exchange) != (bridge.prediction_id, prediction.parent_cycle_id, bridge.underlying_symbol, bridge.underlying_exchange): raise ValueError("bridge prediction mismatch")
    if (lifecycle_context.prediction_id, lifecycle_context.parent_cycle_id, lifecycle_context.underlying_symbol, lifecycle_context.exchange) != (prediction.prediction_id, prediction.parent_cycle_id, prediction.underlying_symbol, prediction.exchange): raise ValueError("lifecycle context mismatch")
    if paper_observation.underlying_symbol != prediction.underlying_symbol: raise ValueError("paper observation underlying mismatch")
    available = paper_observation.data_quality_status == "FRESH"
    if paper_observation.data_quality_status not in {"FRESH", "STALE", "PARTIAL", "INVALID"}: raise ValueError("unknown data quality")
    event = "NONE"
    if lifecycle_fill is not None:
        if type(lifecycle_fill) is not PaperTradeFillV1 or lifecycle_fill.observation_id != paper_observation.observation_id: raise ValueError("persisted fill observation mismatch")
        event = terminal_event_type or _EVENTS.get(lifecycle_fill.fill_reason)
        if event is None: raise ValueError("unmapped lifecycle fill")
        if not available: raise ValueError("lifecycle fill requires fresh evidence")
    elif not available:
        event = "DATA_GAP"
    within = available and lifecycle_context.window_starts_at <= paper_observation.observed_at <= lifecycle_context.entry_window_ends_at
    if event == "ENTRY" and not within: raise ValueError("entry outside prediction entry window")
    return PredictionObservationV1(observation_id=f"prediction-observation:{prediction.prediction_id}:{lifecycle_fill.fill_id if lifecycle_fill else paper_observation.observation_id}", prediction_id=prediction.prediction_id, parent_cycle_id=prediction.parent_cycle_id, underlying_symbol=prediction.underlying_symbol, exchange=prediction.exchange, sequence_number=sequence_number, observed_at=lifecycle_fill.filled_at if lifecycle_fill else paper_observation.observed_at, underlying_price=paper_observation.underlying_last_price if available else None, option_premium=lifecycle_fill.fill_price if lifecycle_fill else paper_observation.option_last_price if available else None, event_type=event, within_entry_window=within, data_available=available, source_observation_id=paper_observation.observation_id)
