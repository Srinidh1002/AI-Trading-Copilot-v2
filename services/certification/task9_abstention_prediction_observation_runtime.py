from __future__ import annotations

from dataclasses import dataclass

from services.certification.task9_abstention_prediction_observation_projection import (
    project_task9_abstention_prediction_observation,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_observation_recorder import (
    Task9PredictionObservationRecorder,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.contracts.market_data_quality_result_v1 import (
    MarketDataQualityResultV1,
)
from services.contracts.market_quote_v1 import (
    MarketQuoteV1,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)


@dataclass(frozen=True, slots=True)
class Task9AbstentionObservationResultV1:
    prediction_id: str
    observation_id: str
    event_type: str
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if not all(
            type(value) is str and value.strip()
            for value in (
                self.prediction_id,
                self.observation_id,
                self.event_type,
            )
        ):
            raise ValueError(
                "Task 9 abstention observation result"
            )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible
            or self.broker_order_submission
        ):
            raise ValueError(
                "Task 9 abstention result safety"
            )


def record_task9_abstention_prediction_observation(
    *,
    prediction_id: str,
    quote: MarketQuoteV1,
    data_quality: MarketDataQualityResultV1,
    prediction_ledger: PredictionLedger,
    lifecycle_context_store: (
        Task9PredictionLifecycleContextStore
    ),
    observation_store: (
        Task9PredictionObservationWindowStore
    ),
) -> Task9AbstentionObservationResultV1:
    if (
        type(prediction_id) is not str
        or not prediction_id.strip()
    ):
        raise ValueError(
            "prediction_id is required"
        )

    if type(prediction_ledger) is not PredictionLedger:
        raise TypeError(
            "prediction_ledger"
        )

    if (
        type(lifecycle_context_store)
        is not Task9PredictionLifecycleContextStore
    ):
        raise TypeError(
            "lifecycle_context_store"
        )

    if (
        type(observation_store)
        is not Task9PredictionObservationWindowStore
    ):
        raise TypeError(
            "observation_store"
        )

    prediction = prediction_ledger.recover(
        prediction_id
    )

    context = lifecycle_context_store.recover(
        prediction_id
    )

    if prediction is None or context is None:
        raise ValueError(
            "Task 9 abstention prediction context unavailable"
        )

    if prediction.predicted_action not in {"WAIT", "NO_TRADE"}:
        raise ValueError(
            "Task 9 abstention runtime requires WAIT or NO_TRADE prediction"
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

    recorder = Task9PredictionObservationRecorder(
        observation_store
    )

    recorded = recorder.record_projected(
        prediction_id=prediction.prediction_id,
        source_observation_id=quote.quote_id,
        event_type=(
            "NONE"
            if (
                data_quality.quality_status
                in {
                    "VALID",
                    "VALID_WITH_WARNINGS",
                }
                and not data_quality.blockers
            )
            else "DATA_GAP"
        ),
        factory=lambda sequence: (
            project_task9_abstention_prediction_observation(
                prediction=prediction,
                lifecycle_context=context,
                quote=quote,
                data_quality=data_quality,
                sequence_number=sequence,
            )
        ),
    )

    return Task9AbstentionObservationResultV1(
        prediction_id=prediction.prediction_id,
        observation_id=recorded.observation_id,
        event_type=recorded.event_type,
    )
