from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_abstention_prediction_observation_runtime import (
    record_task9_abstention_prediction_observation,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.contracts.market_data_provenance_v1 import (
    MarketDataProvenanceV1,
)
from services.contracts.market_data_quality_result_v1 import (
    MarketDataQualityResultV1,
)
from services.contracts.market_quote_v1 import (
    MarketQuoteV1,
)
from services.market_session.policies import (
    MarketSessionPolicy,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from tests.test_task916_prediction_lifecycle_timing_policy import (
    prediction,
)


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(
    2026,
    8,
    10,
    10,
    0,
    tzinfo=IST,
)


def _prediction_pair(
    *,
    action: str,
    observed_at: datetime = NOW,
):
    nifty = prediction(
        action,
        observed_at,
        market="NIFTY",
        exchange="NSE",
    )

    sensex = prediction(
        action,
        observed_at,
        market="SENSEX",
        exchange="BSE",
    )

    return nifty, sensex


def _quote(
    record,
    *,
    quote_id: str,
    observed_at: datetime,
    price: float,
):
    provenance = MarketDataProvenanceV1(
        provider="TEST",
        provider_symbol=record.underlying_symbol,
        provider_exchange=record.exchange,
        source_type="LIVE",
        fetched_at=observed_at,
        received_at=observed_at,
        is_cached=False,
        cache_age_seconds=None,
        provider_request_id=quote_id,
    )

    return MarketQuoteV1(
        quote_id=quote_id,
        underlying_symbol=record.underlying_symbol,
        exchange=record.exchange,
        observed_at=observed_at,
        received_at=observed_at,
        last_price=price,
        previous_close=None,
        open_price=None,
        high_price=None,
        low_price=None,
        volume=None,
        bid_price=None,
        ask_price=None,
        provenance=provenance,
    )


def _quality(
    record,
    quote,
    *,
    status: str = "VALID",
):
    fresh = status in {
        "VALID",
        "VALID_WITH_WARNINGS",
    }

    blockers = (
        ()
        if fresh
        else ("TEST_DATA_GAP",)
    )

    warnings = (
        ("TEST_WARNING",)
        if status == "VALID_WITH_WARNINGS"
        else ()
    )

    return MarketDataQualityResultV1(
        quality_result_id=(
            f"quality:{quote.quote_id}"
        ),
        created_at=quote.received_at,
        subject_type="QUOTE",
        quality_status=status,
        underlying_symbol=record.underlying_symbol,
        exchange=record.exchange,
        observed_at=quote.observed_at,
        received_at=quote.received_at,
        age_seconds=0.0,
        freshness_threshold_seconds=30.0,
        item_count=1,
        valid_item_count=1 if fresh else 0,
        invalid_item_count=0 if fresh else 1,
        duplicate_item_count=0,
        out_of_order_item_count=0,
        incomplete_item_count=0,
        provider_count=1,
        blockers=blockers,
        warnings=warnings,
    )


def _stores(
    tmp_path,
    *,
    action: str = "WAIT",
    observed_at: datetime = NOW,
):
    nifty, sensex = _prediction_pair(
        action=action,
        observed_at=observed_at,
    )

    ledger = PredictionLedger(
        tmp_path / "predictions.json"
    )

    persisted_pair = ledger.save_pair(
        (
            nifty,
            sensex,
        )
    )

    assert persisted_pair == (
        nifty,
        sensex,
    )

    record = nifty

    context = resolve_prediction_lifecycle_window(
        prediction_record=record,
        session_policy=MarketSessionPolicy(),
    )

    context_store = (
        Task9PredictionLifecycleContextStore(
            tmp_path / "contexts.json"
        )
    )

    assert (
        context_store.save(context)
        == "SAVED"
    )

    observation_store = (
        Task9PredictionObservationWindowStore(
            tmp_path / "observations.json"
        )
    )

    return (
        record,
        ledger,
        context_store,
        observation_store,
        context,
    )


def test_wait_records_fresh_underlying_observation_without_p7(
    tmp_path,
):
    (
        record,
        ledger,
        context_store,
        observation_store,
        context,
    ) = _stores(
        tmp_path,
    )

    quote = _quote(
        record,
        quote_id="wait-quote-1",
        observed_at=(
            record.completed_at
            + timedelta(minutes=1)
        ),
        price=(
            record.start_underlying_price
            + 10.0
        ),
    )

    result = (
        record_task9_abstention_prediction_observation(
            prediction_id=record.prediction_id,
            quote=quote,
            data_quality=_quality(
                record,
                quote,
            ),
            prediction_ledger=ledger,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
        )
    )

    assert result.prediction_id == record.prediction_id
    assert result.event_type == "NONE"
    assert result.execution_mode == "PAPER"
    assert (
        result.live_execution_eligible
        is False
    )
    assert (
        result.broker_order_submission
        is False
    )

    recovered = (
        Task9PredictionObservationWindowStore(
            observation_store.file_path
        ).recover(
            record.prediction_id
        )
    )

    assert recovered is not None
    assert recovered.prediction_id == record.prediction_id
    assert recovered.entry_occurred is False
    assert recovered.observation_count == 1
    assert recovered.data_gap_count == 0

    observation = recovered.observations[0]

    assert observation.sequence_number == 1
    assert observation.event_type == "NONE"
    assert observation.data_available is True
    assert (
        observation.source_observation_id
        == quote.quote_id
    )
    assert (
        observation.underlying_price
        == quote.last_price
    )
    assert observation.option_premium is None
    assert observation.within_entry_window is False

    assert (
        quote.observed_at
        <= context.validity_window_ends_at
    )


def test_wait_data_gap_records_no_price(
    tmp_path,
):
    (
        record,
        ledger,
        context_store,
        observation_store,
        _,
    ) = _stores(
        tmp_path,
    )

    quote = _quote(
        record,
        quote_id="wait-gap-1",
        observed_at=(
            record.completed_at
            + timedelta(minutes=1)
        ),
        price=record.start_underlying_price,
    )

    result = (
        record_task9_abstention_prediction_observation(
            prediction_id=record.prediction_id,
            quote=quote,
            data_quality=_quality(
                record,
                quote,
                status="STALE",
            ),
            prediction_ledger=ledger,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
        )
    )

    assert result.event_type == "DATA_GAP"

    recovered = observation_store.recover(
        record.prediction_id
    )

    assert recovered is not None
    assert recovered.entry_occurred is False
    assert recovered.observation_count == 1
    assert recovered.data_gap_count == 1

    observation = recovered.observations[0]

    assert observation.event_type == "DATA_GAP"
    assert observation.data_available is False
    assert observation.underlying_price is None
    assert observation.option_premium is None
    assert (
        observation.source_observation_id
        == quote.quote_id
    )


def test_wait_observation_is_idempotent_across_restart(
    tmp_path,
):
    (
        record,
        ledger,
        context_store,
        observation_store,
        _,
    ) = _stores(
        tmp_path,
    )

    quote = _quote(
        record,
        quote_id="wait-duplicate-1",
        observed_at=(
            record.completed_at
            + timedelta(minutes=1)
        ),
        price=record.start_underlying_price,
    )

    quality = _quality(
        record,
        quote,
    )

    first = (
        record_task9_abstention_prediction_observation(
            prediction_id=record.prediction_id,
            quote=quote,
            data_quality=quality,
            prediction_ledger=ledger,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
        )
    )

    restarted_ledger = PredictionLedger(
        tmp_path / "predictions.json"
    )

    restarted_context_store = (
        Task9PredictionLifecycleContextStore(
            tmp_path / "contexts.json"
        )
    )

    restarted_observation_store = (
        Task9PredictionObservationWindowStore(
            tmp_path / "observations.json"
        )
    )

    assert (
        restarted_ledger.recover(
            record.prediction_id
        )
        == record
    )

    assert (
        restarted_context_store.recover(
            record.prediction_id
        )
        is not None
    )

    second = (
        record_task9_abstention_prediction_observation(
            prediction_id=record.prediction_id,
            quote=quote,
            data_quality=quality,
            prediction_ledger=(
                restarted_ledger
            ),
            lifecycle_context_store=(
                restarted_context_store
            ),
            observation_store=(
                restarted_observation_store
            ),
        )
    )

    assert (
        second.observation_id
        == first.observation_id
    )
    assert second.event_type == first.event_type

    recovered = (
        restarted_observation_store.recover(
            record.prediction_id
        )
    )

    assert recovered is not None
    assert recovered.observation_count == 1
    assert (
        tuple(
            item.sequence_number
            for item in recovered.observations
        )
        == (1,)
    )


def test_wait_records_contiguous_observations_across_restart(
    tmp_path,
):
    (
        record,
        ledger,
        context_store,
        observation_store,
        _,
    ) = _stores(
        tmp_path,
    )

    first_quote = _quote(
        record,
        quote_id="wait-sequence-1",
        observed_at=(
            record.completed_at
            + timedelta(minutes=1)
        ),
        price=(
            record.start_underlying_price
            + 5.0
        ),
    )

    record_task9_abstention_prediction_observation(
        prediction_id=record.prediction_id,
        quote=first_quote,
        data_quality=_quality(
            record,
            first_quote,
        ),
        prediction_ledger=ledger,
        lifecycle_context_store=(
            context_store
        ),
        observation_store=(
            observation_store
        ),
    )

    restarted_ledger = PredictionLedger(
        tmp_path / "predictions.json"
    )

    restarted_context_store = (
        Task9PredictionLifecycleContextStore(
            tmp_path / "contexts.json"
        )
    )

    restarted_observation_store = (
        Task9PredictionObservationWindowStore(
            tmp_path / "observations.json"
        )
    )

    second_quote = _quote(
        record,
        quote_id="wait-sequence-2",
        observed_at=(
            record.completed_at
            + timedelta(minutes=2)
        ),
        price=(
            record.start_underlying_price
            - 5.0
        ),
    )

    record_task9_abstention_prediction_observation(
        prediction_id=record.prediction_id,
        quote=second_quote,
        data_quality=_quality(
            record,
            second_quote,
        ),
        prediction_ledger=restarted_ledger,
        lifecycle_context_store=(
            restarted_context_store
        ),
        observation_store=(
            restarted_observation_store
        ),
    )

    recovered = (
        restarted_observation_store.recover(
            record.prediction_id
        )
    )

    assert recovered is not None
    assert recovered.observation_count == 2

    assert tuple(
        item.sequence_number
        for item in recovered.observations
    ) == (
        1,
        2,
    )

    assert tuple(
        item.source_observation_id
        for item in recovered.observations
    ) == (
        first_quote.quote_id,
        second_quote.quote_id,
    )


def test_wait_accepts_exact_validity_window_boundary(
    tmp_path,
):
    (
        record,
        ledger,
        context_store,
        observation_store,
        context,
    ) = _stores(
        tmp_path,
    )

    quote = _quote(
        record,
        quote_id="wait-validity-boundary",
        observed_at=(
            context.validity_window_ends_at
        ),
        price=record.start_underlying_price,
    )

    result = (
        record_task9_abstention_prediction_observation(
            prediction_id=record.prediction_id,
            quote=quote,
            data_quality=_quality(
                record,
                quote,
            ),
            prediction_ledger=ledger,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
        )
    )

    assert result.event_type == "NONE"

    recovered = observation_store.recover(
        record.prediction_id
    )

    assert recovered is not None
    assert recovered.observation_count == 1
    assert (
        recovered.observations[0].observed_at
        == context.validity_window_ends_at
    )


def test_wait_rejects_observation_after_validity_window(
    tmp_path,
):
    (
        record,
        ledger,
        context_store,
        observation_store,
        context,
    ) = _stores(
        tmp_path,
    )

    quote = _quote(
        record,
        quote_id="wait-after-validity",
        observed_at=(
            context.validity_window_ends_at
            + timedelta(seconds=1)
        ),
        price=record.start_underlying_price,
    )

    with pytest.raises(
        ValueError,
        match="validity window",
    ):
        record_task9_abstention_prediction_observation(
            prediction_id=record.prediction_id,
            quote=quote,
            data_quality=_quality(
                record,
                quote,
            ),
            prediction_ledger=ledger,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
        )

    recovered = observation_store.recover(
        record.prediction_id
    )

    assert recovered is not None
    assert recovered.observation_count == 0


def test_non_wait_prediction_is_rejected(
    tmp_path,
):
    (
        record,
        ledger,
        context_store,
        observation_store,
        _,
    ) = _stores(
        tmp_path,
        action="CALL",
    )

    quote = _quote(
        record,
        quote_id="call-quote",
        observed_at=(
            record.completed_at
            + timedelta(minutes=1)
        ),
        price=record.start_underlying_price,
    )

    with pytest.raises(
        ValueError,
        match="non-entry observation cannot be used for selected directional prediction",
    ):
        record_task9_abstention_prediction_observation(
            prediction_id=record.prediction_id,
            quote=quote,
            data_quality=_quality(
                record,
                quote,
            ),
            prediction_ledger=ledger,
            lifecycle_context_store=(
                context_store
            ),
            observation_store=(
                observation_store
            ),
        )