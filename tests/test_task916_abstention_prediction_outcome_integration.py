from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_abstention_prediction_observation_runtime import (
    record_task9_abstention_prediction_observation,
)
from services.certification.task9_live_paper_trade_counting_evaluator import (
    evaluate_task9_live_paper_trade_counting,
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
from services.contracts.market_quote_v1 import MarketQuoteV1
from services.contracts.prediction_lifecycle_outcome_input_v1 import (
    PredictionLifecycleOutcomeInputV1,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.contracts.task9_live_paper_trade_counting_input_v1 import (
    Task9LivePaperTradeCountingInputV1,
)
from services.market_session.policies import MarketSessionPolicy
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.prediction_outcomes.prediction_lifecycle_outcome_evaluator import (
    evaluate_prediction_lifecycle_outcome,
)
from tests.test_task916_prediction_lifecycle_timing_policy import prediction


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 8, 10, 10, 0, tzinfo=IST)


def _pair(action: str):
    return (
        prediction(
            action,
            NOW,
            market="NIFTY",
            exchange="NSE",
        ),
        prediction(
            action,
            NOW,
            market="SENSEX",
            exchange="BSE",
        ),
    )


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

    return MarketDataQualityResultV1(
        quality_result_id=f"quality:{quote.quote_id}",
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
        blockers=() if fresh else ("TEST_DATA_GAP",),
        warnings=(),
    )


def _setup(tmp_path, action: str):
    nifty, sensex = _pair(action)

    prediction_path = tmp_path / "predictions.json"
    context_path = tmp_path / "contexts.json"
    observation_path = tmp_path / "observations.json"

    ledger = PredictionLedger(prediction_path)
    ledger.save_pair((nifty, sensex))

    context = resolve_prediction_lifecycle_window(
        prediction_record=nifty,
        session_policy=MarketSessionPolicy(),
    )

    context_store = Task9PredictionLifecycleContextStore(
        context_path
    )
    context_store.save(context)

    observation_store = (
        Task9PredictionObservationWindowStore(
            observation_path
        )
    )

    return (
        nifty,
        context,
        prediction_path,
        context_path,
        observation_path,
        ledger,
        context_store,
        observation_store,
    )


def _record_quote(
    *,
    record,
    quote,
    quality,
    ledger,
    context_store,
    observation_store,
):
    return record_task9_abstention_prediction_observation(
        prediction_id=record.prediction_id,
        quote=quote,
        data_quality=quality,
        prediction_ledger=ledger,
        lifecycle_context_store=context_store,
        observation_store=observation_store,
    )


def _evaluate(
    *,
    record,
    window,
    evaluated_at,
):
    return evaluate_prediction_lifecycle_outcome(
        PredictionLifecycleOutcomeInputV1(
            prediction=record,
            observation_window=window,
            policy=PredictionLifecycleOutcomePolicyV1(
                policy_id="task9-abstention-outcome-policy",
                policy_version="1.0",
            ),
            evaluated_at=evaluated_at,
        )
    )


@pytest.mark.parametrize(
    "action",
    (
        "WAIT",
        "NO_TRADE",
    ),
)
@pytest.mark.parametrize(
    ("price", "expected_outcome"),
    (
        (25020.0, "NO_TRADE_CORRECT"),
        (25060.0, "NO_TRADE_MISSED_MOVE"),
    ),
)
def test_abstention_prediction_resolves_from_durable_underlying_evidence_after_restart(
    tmp_path,
    action,
    price,
    expected_outcome,
):
    (
        record,
        context,
        prediction_path,
        context_path,
        observation_path,
        ledger,
        context_store,
        observation_store,
    ) = _setup(
        tmp_path,
        action,
    )

    quote = _quote(
        record,
        quote_id=f"{action.lower()}-objective-quote",
        observed_at=(
            record.completed_at
            + timedelta(minutes=1)
        ),
        price=price,
    )

    result = _record_quote(
        record=record,
        quote=quote,
        quality=_quality(record, quote),
        ledger=ledger,
        context_store=context_store,
        observation_store=observation_store,
    )

    assert result.event_type == "NONE"

    # Cold restart: no in-memory prediction/context/window authority retained.
    restarted_ledger = PredictionLedger(
        prediction_path
    )
    restarted_context_store = (
        Task9PredictionLifecycleContextStore(
            context_path
        )
    )
    restarted_observation_store = (
        Task9PredictionObservationWindowStore(
            observation_path
        )
    )

    recovered_prediction = restarted_ledger.recover(
        record.prediction_id
    )
    recovered_context = restarted_context_store.recover(
        record.prediction_id
    )
    recovered_window = restarted_observation_store.recover(
        record.prediction_id
    )

    assert recovered_prediction == record
    assert recovered_context == context
    assert recovered_window is not None

    assert recovered_window.entry_occurred is False
    assert recovered_window.observation_count == 1
    assert recovered_window.data_gap_count == 0
    assert (
        recovered_window.highest_underlying_price
        == price
    )
    assert (
        recovered_window.lowest_underlying_price
        == price
    )

    outcome = _evaluate(
        record=recovered_prediction,
        window=recovered_window,
        evaluated_at=context.validity_window_ends_at,
    )

    assert outcome.predicted_action == action
    assert outcome.evaluation_status == "RESOLVED"
    assert outcome.outcome == expected_outcome
    assert outcome.entry_occurred is False
    assert outcome.highest_target_reached == 0
    assert outcome.execution_mode == "PAPER"
    assert outcome.live_execution_eligible is False
    assert outcome.broker_order_submission is False

    count_decision = (
        evaluate_task9_live_paper_trade_counting(
            Task9LivePaperTradeCountingInputV1(
                prediction=recovered_prediction,
                lifecycle_outcome=outcome,
                reconciliation=None,
                record_source="LIVE_REAL_TIME",
                session_status=(
                    "REAL_TIME_MARKET_SESSION"
                ),
                evidence_status="VALID",
                official_run_id="task916-run",
                record_run_id="task916-run",
                official_start_at=(
                    record.completed_at
                    - timedelta(seconds=1)
                ),
                evaluated_at=(
                    context.validity_window_ends_at
                ),
            )
        )
    )

    assert count_decision.trade_target_countable is False


@pytest.mark.parametrize(
    "action",
    (
        "WAIT",
        "NO_TRADE",
    ),
)
def test_abstention_data_gap_fails_closed_after_restart(
    tmp_path,
    action,
):
    (
        record,
        context,
        prediction_path,
        context_path,
        observation_path,
        ledger,
        context_store,
        observation_store,
    ) = _setup(
        tmp_path,
        action,
    )

    quote = _quote(
        record,
        quote_id=f"{action.lower()}-gap-quote",
        observed_at=(
            record.completed_at
            + timedelta(minutes=1)
        ),
        price=record.start_underlying_price,
    )

    result = _record_quote(
        record=record,
        quote=quote,
        quality=_quality(
            record,
            quote,
            status="STALE",
        ),
        ledger=ledger,
        context_store=context_store,
        observation_store=observation_store,
    )

    assert result.event_type == "DATA_GAP"

    recovered_prediction = PredictionLedger(
        prediction_path
    ).recover(
        record.prediction_id
    )

    recovered_context = (
        Task9PredictionLifecycleContextStore(
            context_path
        ).recover(
            record.prediction_id
        )
    )

    recovered_window = (
        Task9PredictionObservationWindowStore(
            observation_path
        ).recover(
            record.prediction_id
        )
    )

    assert recovered_prediction is not None
    assert recovered_context is not None
    assert recovered_window is not None

    assert recovered_window.entry_occurred is False
    assert recovered_window.data_gap_count == 1
    assert recovered_window.highest_underlying_price is None
    assert recovered_window.lowest_underlying_price is None

    outcome = _evaluate(
        record=recovered_prediction,
        window=recovered_window,
        evaluated_at=(
            recovered_context.validity_window_ends_at
        ),
    )

    assert outcome.predicted_action == action
    assert (
        outcome.evaluation_status
        == "DATA_UNAVAILABLE"
    )
    assert outcome.outcome == "DATA_UNAVAILABLE"
    assert (
        "OBSERVATION_WINDOW_CONTAINS_DATA_GAP"
        in outcome.blockers
    )

    count_decision = (
        evaluate_task9_live_paper_trade_counting(
            Task9LivePaperTradeCountingInputV1(
                prediction=recovered_prediction,
                lifecycle_outcome=outcome,
                reconciliation=None,
                record_source="LIVE_REAL_TIME",
                session_status=(
                    "REAL_TIME_MARKET_SESSION"
                ),
                evidence_status="VALID",
                official_run_id="task916-run",
                record_run_id="task916-run",
                official_start_at=(
                    record.completed_at
                    - timedelta(seconds=1)
                ),
                evaluated_at=(
                    recovered_context
                    .validity_window_ends_at
                ),
            )
        )
    )

    assert count_decision.trade_target_countable is False