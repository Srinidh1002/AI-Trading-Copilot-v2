"""Provider-free recovery of durable unresolved Task 9 abstentions."""
from __future__ import annotations

from datetime import datetime

from services.certification.task9_abstention_prediction_observation_runtime import record_task9_abstention_prediction_observation
from services.certification.task9_prediction_lifecycle_context_store import Task9PredictionLifecycleContextStore
from services.certification.task9_prediction_lifecycle_outcome_store import Task9PredictionLifecycleOutcomeStore
from services.certification.task9_prediction_observation_window_store import Task9PredictionObservationWindowStore
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_quote_v1 import MarketQuoteV1
from services.contracts.prediction_record_v1 import prediction_record_from_dict
from services.contracts.prediction_lifecycle_outcome_input_v1 import PredictionLifecycleOutcomeInputV1
from services.contracts.prediction_lifecycle_outcome_policy_v1 import PredictionLifecycleOutcomePolicyV1
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.prediction_outcomes.prediction_lifecycle_outcome_evaluator import evaluate_prediction_lifecycle_outcome


def recover_task9_later_abstention_observations(*, market, exchange, quote, data_quality, prediction_ledger, lifecycle_context_store, observation_store, outcome_store, outcome_policy, evaluated_at):
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
        if (prediction.underlying_symbol, prediction.exchange) != (market, exchange) or prediction.predicted_action not in {"WAIT", "NO_TRADE"}:
            continue
        if outcome_store.recover(prediction.prediction_id) is not None:
            continue
        context = lifecycle_context_store.recover(prediction.prediction_id)
        if context is None:
            raise ValueError("Task9 abstention lifecycle context unavailable")
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


def finalize_task9_expired_abstentions(*, prediction_ledger, lifecycle_context_store, observation_store, outcome_store, outcome_policy, evaluated_at):
    """Provider-free terminal evaluation of already-durable expired abstentions."""
    if type(prediction_ledger) is not PredictionLedger or type(lifecycle_context_store) is not Task9PredictionLifecycleContextStore or type(observation_store) is not Task9PredictionObservationWindowStore or type(outcome_store) is not Task9PredictionLifecycleOutcomeStore or type(outcome_policy) is not PredictionLifecycleOutcomePolicyV1 or not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise TypeError("Task9 expired abstention drain input")
    finalized = []
    for raw in prediction_ledger.all_records():
        prediction = prediction_record_from_dict(raw)
        if prediction.predicted_action not in {"WAIT", "NO_TRADE"} or prediction.terminal_status != "COMPLETED" or outcome_store.recover(prediction.prediction_id) is not None:
            continue
        context = lifecycle_context_store.recover(prediction.prediction_id)
        if context is None:
            raise ValueError("Task9 abstention lifecycle context unavailable")
        if (context.prediction_id, context.parent_cycle_id, context.underlying_symbol, context.exchange, context.action) != (prediction.prediction_id, prediction.parent_cycle_id, prediction.underlying_symbol, prediction.exchange, prediction.predicted_action):
            raise ValueError("Task9 abstention lifecycle context identity")
        window = observation_store.recover(prediction.prediction_id)
        if window is None or window.validity_window_ends_at > evaluated_at:
            continue
        candidate = evaluate_prediction_lifecycle_outcome(PredictionLifecycleOutcomeInputV1(prediction=prediction, observation_window=window, policy=outcome_policy, evaluated_at=evaluated_at))
        if candidate.evaluation_status == "UNRESOLVED":
            raise ValueError("Task9 expired abstention remained unresolved")
        outcome_store.save(candidate)
        finalized.append(prediction.prediction_id)
    return tuple(finalized)
