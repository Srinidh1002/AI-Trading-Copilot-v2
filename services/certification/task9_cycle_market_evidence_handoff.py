"""Immutable, cycle-scoped handoff of already-acquired Task 8 evidence to Task 9."""
from __future__ import annotations

from dataclasses import dataclass

from services.analysis.live_market_candidate_evaluator import LiveMarketCandidateEvaluationResultV1
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_quote_v1 import MarketQuoteV1
from services.contracts.paper_market_observation_v1 import PaperMarketObservationV1
from services.contracts.paper_orchestration_cycle_input_v1 import PaperOrchestrationCycleInputV1
from services.contracts.prediction_lifecycle_timing_v1 import (
    PredictionLifecycleWindowV1,
)
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    SelectedMarketP6PlanningResultV1,
)


@dataclass(frozen=True, slots=True)
class Task9CycleMarketEvidenceV1:
    """Exact evidence retained from one current authoritative market cycle.

    Optional quote/quality/P7 fields are deliberately absent until their
    existing certified producer constructs them; this contract never adapts
    metadata into new market evidence.
    """
    prediction: PredictionRecordV1
    cycle: PaperOrchestrationCycleInputV1
    evaluation: LiveMarketCandidateEvaluationResultV1 | None = None
    market_quote: MarketQuoteV1 | None = None
    data_quality: MarketDataQualityResultV1 | None = None
    lifecycle_window: PredictionLifecycleWindowV1 | None = None
    selected_planning: SelectedMarketP6PlanningResultV1 | None = None
    paper_observation: PaperMarketObservationV1 | None = None
    provider_incidents: tuple[Task9ProviderIncidentV1, ...] = ()
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if type(self.prediction) is not PredictionRecordV1 or type(self.cycle) is not PaperOrchestrationCycleInputV1:
            raise TypeError("prediction/cycle")
        identity = (self.prediction.underlying_symbol, self.prediction.exchange)
        if identity not in {("NIFTY", "NSE"), ("SENSEX", "BSE")} or identity != (self.cycle.underlying_symbol, self.cycle.exchange):
            raise ValueError("market identity")
        if self.evaluation is not None:
            if type(self.evaluation) is not LiveMarketCandidateEvaluationResultV1 or self.evaluation.candidate.observation_id != self.cycle.observation_id:
                raise ValueError("evaluation identity")
            if self.prediction.terminal_status != "COMPLETED":
                raise ValueError("non-completed prediction cannot retain evaluation")
        if self.lifecycle_window is not None:
            if type(self.lifecycle_window) is not PredictionLifecycleWindowV1:
                raise TypeError("lifecycle_window")
            if (
                self.lifecycle_window.prediction_id
                != self.prediction.prediction_id
                or self.lifecycle_window.parent_cycle_id
                != self.prediction.parent_cycle_id
                or self.lifecycle_window.underlying_symbol != identity[0]
                or self.lifecycle_window.exchange != identity[1]
            ):
                raise ValueError("lifecycle window identity")
        if self.selected_planning is not None:
            if type(self.selected_planning) is not SelectedMarketP6PlanningResultV1:
                raise TypeError("selected_planning")
            if (
                self.selected_planning.bridge.selected_market != identity
                or self.selected_planning.bridge.observation_id
                != self.cycle.observation_id
            ):
                raise ValueError("selected planning identity")
            if self.evaluation is None:
                raise ValueError("selected planning requires evaluation")
        if (self.market_quote is None) != (self.data_quality is None):
            raise ValueError("market_quote and data_quality must be supplied together")
        if (
            self.prediction.terminal_status in {"FAILED", "UNAVAILABLE"}
            and self.market_quote is not None
        ):
            raise ValueError("failed prediction cannot retain quote evidence")
        if self.market_quote is not None:
            if type(self.market_quote) is not MarketQuoteV1:
                raise TypeError("market_quote")
            if (
                self.market_quote.underlying_symbol,
                self.market_quote.exchange,
            ) != identity:
                raise ValueError("market_quote identity")
        if self.data_quality is not None:
            if type(self.data_quality) is not MarketDataQualityResultV1:
                raise TypeError("data_quality")
            if self.data_quality.subject_type != "QUOTE":
                raise ValueError("data_quality subject_type")
            if (
                self.data_quality.underlying_symbol,
                self.data_quality.exchange,
            ) != identity:
                raise ValueError("data_quality identity")
        if (
            self.market_quote is not None
            and self.data_quality is not None
            and (
                self.data_quality.observed_at
                != self.market_quote.observed_at
                or self.data_quality.received_at
                != self.market_quote.received_at
            )
        ):
            raise ValueError("quote/quality timestamps")
        if self.paper_observation is not None:
            if type(self.paper_observation) is not PaperMarketObservationV1 or self.paper_observation.underlying_symbol != identity[0]: raise ValueError("paper observation identity")
            if self.evaluation is None:
                raise ValueError("paper observation requires evaluation")
        if self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible: raise ValueError("PAPER-only handoff")
        if any(type(item) is not Task9ProviderIncidentV1 or item.exchange != identity[1] for item in self.provider_incidents): raise ValueError("provider_incidents")
        object.__setattr__(self, "provider_incidents", tuple(self.provider_incidents))
@dataclass(frozen=True, slots=True)
class Task9ProviderIncidentV1:
    incident_id: str
    endpoint: str
    exchange: str
    timeframe: str
    failure_reason: str
    provider_result: str
    provider_attempted: bool
    def __post_init__(self):
        if (not isinstance(self.incident_id,str) or not self.incident_id or self.endpoint != "historical-data" or self.exchange not in {"NSE","BSE"} or self.timeframe not in {"5m","15m","1h","1d"} or self.failure_reason != "HISTORICAL-DATA_RATE_LIMITED" or self.provider_result != "RATE_LIMITED" or self.provider_attempted is not True): raise ValueError("provider incident")
