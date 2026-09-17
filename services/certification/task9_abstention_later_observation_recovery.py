"""Provider-free recovery of durable unresolved Task 9 abstentions."""
from __future__ import annotations

from datetime import datetime

from services.certification.task9_abstention_prediction_observation_runtime import record_task9_abstention_prediction_observation
from services.certification.task9_prediction_observation_recorder import Task9PredictionObservationRecorder
from services.contracts.prediction_observation_v1 import PredictionObservationV1
from services.market.task9_live_tick_stream import Task9LiveTickJournal
from services.certification.task9_prediction_lifecycle_context_store import Task9PredictionLifecycleContextStore
from services.certification.task9_lifecycle_context_recovery import recover_or_reconstruct_task9_lifecycle_context
from services.certification.task9_prediction_lifecycle_outcome_store import Task9PredictionLifecycleOutcomeStore
from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_quote_v1 import MarketQuoteV1
from services.contracts.prediction_record_v1 import prediction_record_from_dict
from services.contracts.prediction_lifecycle_outcome_input_v1 import PredictionLifecycleOutcomeInputV1
from services.contracts.prediction_lifecycle_outcome_policy_v1 import PredictionLifecycleOutcomePolicyV1
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.market_session.policies import MarketSessionPolicy
from services.prediction_outcomes.prediction_lifecycle_outcome_evaluator import evaluate_prediction_lifecycle_outcome


def recover_task9_later_abstention_observations(*, market, exchange, quote, data_quality, prediction_ledger, lifecycle_context_store, observation_store, outcome_store, outcome_policy, evaluated_at, session_policy=MarketSessionPolicy()):
    """Record only current, genuinely later evidence for matching unresolved abstentions."""
    if (market, exchange) not in {("NIFTY", "NSE"), ("SENSEX", "BSE")}:
        raise ValueError("Task9 market identity")
    if type(quote) is not MarketQuoteV1 or type(data_quality) is not MarketDataQualityResultV1:
        raise TypeError("Task9 abstention current evidence")
    if (quote.underlying_symbol, quote.exchange) != (market, exchange) or (data_quality.underlying_symbol, data_quality.exchange) != (market, exchange):
        raise ValueError("Task9 abstention evidence identity")
    if data_quality.observed_at != quote.observed_at or data_quality.received_at != quote.received_at:
        raise ValueError("Task9 abstention evidence timestamp")
    recovered = []
    for raw in prediction_ledger.all_records():
        prediction = prediction_record_from_dict(raw)

        # Failed/unavailable child predictions are durable exclusions,
        # not completed WAIT/NO_TRADE lifecycle abstentions. They remain
        # persisted and reportable through the child-failure authority,
        # but must never enter abstention lifecycle reconstruction.
        if prediction.terminal_status != "COMPLETED":
            continue

        non_entry_prediction = (
            prediction.predicted_action in {"WAIT", "NO_TRADE"}
            or (
                prediction.predicted_action in {"CALL", "PUT"}
                and not prediction.parent_selected
            )
        )
        if (
            (prediction.underlying_symbol, prediction.exchange)
            != (market, exchange)
            or not non_entry_prediction
        ):
            continue
        if outcome_store.recover(prediction.prediction_id) is not None:
            continue
        context = recover_or_reconstruct_task9_lifecycle_context(
            prediction=prediction,
            lifecycle_context_store=lifecycle_context_store,
            session_policy=session_policy,
        ).context
        if (
            context.prediction_id != prediction.prediction_id
            or context.parent_cycle_id != prediction.parent_cycle_id
            or (context.underlying_symbol, context.exchange)
            != (prediction.underlying_symbol, prediction.exchange)
            or context.action != prediction.predicted_action
        ):
            raise ValueError("Task9 abstention lifecycle context identity")
        window = observation_store.recover(prediction.prediction_id)
        if window is None:
            continue

        append_current_observation = (
            prediction.completed_at < quote.observed_at
            <= context.validity_window_ends_at
        )
        if append_current_observation:
            record_task9_abstention_prediction_observation(prediction_id=prediction.prediction_id, quote=quote, data_quality=data_quality, prediction_ledger=prediction_ledger, lifecycle_context_store=lifecycle_context_store, observation_store=observation_store)
            window = observation_store.recover(prediction.prediction_id)

        finalize_existing_window = (
            evaluated_at >= context.validity_window_ends_at
            or window.session_closed
            or window.expiry_reached
        )
        if not append_current_observation and not finalize_existing_window:
            continue
        candidate = evaluate_prediction_lifecycle_outcome(PredictionLifecycleOutcomeInputV1(prediction=prediction, observation_window=window, policy=outcome_policy, evaluated_at=evaluated_at))
        if candidate.evaluation_status != "UNRESOLVED":
            outcome_store.save(candidate)
        if append_current_observation:
            recovered.append(prediction.prediction_id)
    return tuple(recovered)


def _backfill_empty_abstention_window_from_live_ticks(
    *,
    prediction,
    context,
    observation_store,
    live_stream_root,
    evaluated_at,
):
    """Project genuine durable WS extrema into one empty abstention window.

    This is strictly a durable-evidence recovery seam.  It performs no
    provider call and never manufactures a quote, option premium, or price.
    """

    window = observation_store.recover(
        prediction.prediction_id
    )

    if window is None:
        return None

    if (
        window.highest_underlying_price is not None
        and window.lowest_underlying_price is not None
    ):
        return window

    # A non-empty window has its own ordered evidence authority.  Do not
    # insert older WS observations around already-persisted observations.
    # DATA_GAP windows also remain fail-closed under the existing policy.
    if window.observation_count != 0:
        return window

    if live_stream_root is None:
        return window

    ticks = Task9LiveTickJournal(
        live_stream_root
    ).load(
        context.validity_window_ends_at.date()
    )

    candidates = tuple(
        tick
        for tick in ticks
        if (
            (
                tick.market,
                tick.exchange,
            )
            == (
                prediction.underlying_symbol,
                prediction.exchange,
            )
            and prediction.completed_at
            < tick.provider_timestamp
            <= context.validity_window_ends_at
            and tick.received_at <= evaluated_at
        )
    )

    if not candidates:
        return window

    low_tick = min(
        candidates,
        key=lambda tick: (
            tick.ltp,
            tick.provider_timestamp,
            tick.received_at,
        ),
    )

    high_tick = max(
        candidates,
        key=lambda tick: (
            tick.ltp,
            tick.provider_timestamp,
            tick.received_at,
        ),
    )

    selected = [low_tick]

    if high_tick.ltp != low_tick.ltp:
        selected.append(
            high_tick
        )

    selected.sort(
        key=lambda tick: (
            tick.provider_timestamp,
            tick.received_at,
            tick.ltp,
        )
    )

    recorder = Task9PredictionObservationRecorder(
        observation_store
    )

    for tick in selected:

        source_observation_id = (
            "task9-live-tick:"
            f"{tick.exchange}:"
            f"{tick.symbol_token}:"
            f"{tick.provider_timestamp.isoformat()}:"
            f"{format(tick.ltp, '.12g')}"
        )

        observation_id = (
            "prediction-observation:"
            f"{prediction.prediction_id}:"
            f"{source_observation_id}"
        )

        recorder.record_projected(
            prediction_id=prediction.prediction_id,
            source_observation_id=source_observation_id,
            event_type="NONE",
            factory=lambda sequence, tick=tick, observation_id=observation_id, source_observation_id=source_observation_id: PredictionObservationV1(
                observation_id=observation_id,
                prediction_id=prediction.prediction_id,
                parent_cycle_id=prediction.parent_cycle_id,
                underlying_symbol=prediction.underlying_symbol,
                exchange=prediction.exchange,
                sequence_number=sequence,
                observed_at=tick.provider_timestamp,
                underlying_price=tick.ltp,
                option_premium=None,
                event_type="NONE",
                within_entry_window=(
                    tick.provider_timestamp
                    <= context.entry_window_ends_at
                ),
                data_available=True,
                source_observation_id=source_observation_id,
            ),
        )

    return observation_store.recover(
        prediction.prediction_id
    )


def finalize_task9_expired_abstentions(*, prediction_ledger, lifecycle_context_store, observation_store, outcome_store, outcome_policy, evaluated_at, session_policy=MarketSessionPolicy(), live_stream_root=None):
    """Provider-free terminal evaluation of already-durable expired abstentions."""
    if type(prediction_ledger) is not PredictionLedger or type(lifecycle_context_store) is not Task9PredictionLifecycleContextStore or type(observation_store) is not Task9PredictionObservationWindowStore or type(outcome_store) is not Task9PredictionLifecycleOutcomeStore or type(outcome_policy) is not PredictionLifecycleOutcomePolicyV1 or not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise TypeError("Task9 expired abstention drain input")
    finalized = []
    for raw in prediction_ledger.all_records():
        prediction = prediction_record_from_dict(raw)
        abstention_prediction = (
            prediction.predicted_action in {"WAIT", "NO_TRADE"}
        )
        if (
            not abstention_prediction
            or prediction.terminal_status != "COMPLETED"
            or outcome_store.recover(prediction.prediction_id) is not None
        ):
            continue
        context = recover_or_reconstruct_task9_lifecycle_context(
            prediction=prediction,
            lifecycle_context_store=lifecycle_context_store,
            session_policy=session_policy,
        ).context
        if (context.prediction_id, context.parent_cycle_id, context.underlying_symbol, context.exchange, context.action) != (prediction.prediction_id, prediction.parent_cycle_id, prediction.underlying_symbol, prediction.exchange, prediction.predicted_action):
            raise ValueError("Task9 abstention lifecycle context identity")
        window = observation_store.recover(
            prediction.prediction_id
        )
        if window is None:
            # A missing historical window may only be reconstructed when
            # durable live-stream evidence is available. Without that
            # evidence source, preserve the existing fail-closed behavior.
            if live_stream_root is None:
                continue

            observation_store.initialize(
                prediction=prediction,
                entry_window_ends_at=context.entry_window_ends_at,
                validity_window_ends_at=(
                    context.validity_window_ends_at
                ),
            )
            window = observation_store.recover(
                prediction.prediction_id
            )
            if window is None:
                raise ValueError(
                    "Task9 abstention observation window reconstruction"
                )

        if window.validity_window_ends_at > evaluated_at:
            continue

        window = _backfill_empty_abstention_window_from_live_ticks(
            prediction=prediction,
            context=context,
            observation_store=observation_store,
            live_stream_root=live_stream_root,
            evaluated_at=evaluated_at,
        )

        if window is None:
            continue

        candidate = evaluate_prediction_lifecycle_outcome(PredictionLifecycleOutcomeInputV1(prediction=prediction, observation_window=window, policy=outcome_policy, evaluated_at=evaluated_at))
        if candidate.evaluation_status == "UNRESOLVED":
            raise ValueError("Task9 expired abstention remained unresolved")
        outcome_store.save(candidate)
        finalized.append(prediction.prediction_id)
    return tuple(finalized)
