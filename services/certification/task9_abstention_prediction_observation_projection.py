from __future__ import annotations

from services.contracts.market_data_quality_result_v1 import (
    MarketDataQualityResultV1,
)
from services.contracts.market_quote_v1 import (
    MarketQuoteV1,
)
from services.contracts.prediction_lifecycle_timing_v1 import (
    PredictionLifecycleWindowV1,
)
from services.contracts.prediction_observation_v1 import (
    PredictionObservationV1,
)
from services.contracts.prediction_record_v1 import (
    PredictionRecordV1,
)


_FRESH_QUALITY = {
    "VALID",
    "VALID_WITH_WARNINGS",
}


def project_task9_abstention_prediction_observation(
    *,
    prediction: PredictionRecordV1,
    lifecycle_context: PredictionLifecycleWindowV1,
    quote: MarketQuoteV1,
    data_quality: MarketDataQualityResultV1,
    sequence_number: int,
) -> PredictionObservationV1:
    if type(prediction) is not PredictionRecordV1:
        raise TypeError(
            "prediction must be exact PredictionRecordV1"
        )

    if (
        type(lifecycle_context)
        is not PredictionLifecycleWindowV1
    ):
        raise TypeError(
            "lifecycle_context must be exact "
            "PredictionLifecycleWindowV1"
        )

    if type(quote) is not MarketQuoteV1:
        raise TypeError(
            "quote must be exact MarketQuoteV1"
        )

    if (
        type(data_quality)
        is not MarketDataQualityResultV1
    ):
        raise TypeError(
            "data_quality must be exact "
            "MarketDataQualityResultV1"
        )

    if (
        type(sequence_number) is not int
        or isinstance(sequence_number, bool)
        or sequence_number <= 0
    ):
        raise ValueError(
            "sequence_number must be positive"
        )

    if (
        prediction.predicted_action in {"CALL", "PUT"}
        and prediction.parent_selected
    ):
        raise ValueError(
            "non-entry observation cannot be used for selected directional prediction"
        )

    expected_identity = (
        prediction.underlying_symbol,
        prediction.exchange,
    )

    if (
        quote.underlying_symbol,
        quote.exchange,
    ) != expected_identity:
        raise ValueError(
            "quote/prediction identity mismatch"
        )

    quality_identity = (
        data_quality.underlying_symbol,
        data_quality.exchange,
    )

    if quality_identity != expected_identity:
        raise ValueError(
            "quality/prediction identity mismatch"
        )

    if (
        lifecycle_context.prediction_id
        != prediction.prediction_id
    ):
        raise ValueError(
            "lifecycle context/prediction identity mismatch"
        )

    if quote.observed_at < prediction.completed_at:
        raise ValueError(
            "quote precedes prediction completion"
        )

    if (
        quote.observed_at
        > lifecycle_context.validity_window_ends_at
    ):
        raise ValueError(
            "quote exceeds prediction validity window"
        )

    if (
        data_quality.observed_at is not None
        and data_quality.observed_at
        != quote.observed_at
    ):
        raise ValueError(
            "quality/quote observed_at mismatch"
        )

    if (
        data_quality.received_at is not None
        and data_quality.received_at
        != quote.received_at
    ):
        raise ValueError(
            "quality/quote received_at mismatch"
        )

    fresh = (
        data_quality.quality_status
        in _FRESH_QUALITY
        and not data_quality.blockers
    )

    event_type = (
        "NONE"
        if fresh
        else "DATA_GAP"
    )

    return PredictionObservationV1(
        observation_id=(
            f"{prediction.prediction_id}:"
            f"observation:{sequence_number}"
        ),
        prediction_id=prediction.prediction_id,
        parent_cycle_id=prediction.parent_cycle_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        sequence_number=sequence_number,
        observed_at=quote.observed_at,
        underlying_price=(
            quote.last_price
            if fresh
            else None
        ),
        option_premium=None,
        event_type=event_type,
        source_observation_id=quote.quote_id,
        data_available=fresh,
        within_entry_window=False,
        execution_mode="PAPER",
        live_execution_eligible=False,
        broker_order_submission=False,
        
    )
