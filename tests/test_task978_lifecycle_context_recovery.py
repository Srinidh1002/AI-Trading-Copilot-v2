"""Crash-boundary regression coverage for Task 9 lifecycle context recovery."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from services.certification.task9_abstention_later_observation_recovery import (
    recover_task9_later_abstention_observations,
)
from services.certification.task9_lifecycle_context_recovery import (
    recover_or_reconstruct_task9_lifecycle_context,
)
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.market_session.policies import MarketSessionPolicy
from tests.test_task916_production_child_evidence_authority import (
    _authority,
    _quote,
    _runtime,
)


def _policy():
    return PredictionLifecycleOutcomePolicyV1(
        policy_id="task978-policy",
        policy_version="1.0",
    )


def _remove_context(store, prediction_id):
    document = store._read()
    del document["contexts"][prediction_id]
    store._write(document)


def _recover(runtime, prediction, quote, quality):
    return recover_task9_later_abstention_observations(
        market=prediction.underlying_symbol,
        exchange=prediction.exchange,
        quote=quote,
        data_quality=quality,
        prediction_ledger=runtime["ledger"],
        lifecycle_context_store=runtime["context_store"],
        observation_store=runtime["observation_store"],
        outcome_store=runtime["outcome_store"],
        outcome_policy=_policy(),
        evaluated_at=quote.observed_at,
        session_policy=MarketSessionPolicy(),
    )


def test_missing_sensex_wait_context_reconstructs_canonically_and_child_recovers(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="WAIT")
    prediction = runtime["predictions"][1]
    _remove_context(runtime["context_store"], prediction.prediction_id)

    result = _authority(runtime)("SENSEX", "BSE", False)
    expected = resolve_prediction_lifecycle_window(
        prediction_record=prediction,
        session_policy=MarketSessionPolicy(),
    )

    assert runtime["context_store"].recover(prediction.prediction_id) == expected
    assert result.prediction == prediction
    assert result.prediction.execution_mode == "PAPER"
    assert result.prediction.broker_order_submission is False
    assert result.prediction.live_execution_eligible is False
    assert runtime["binding_store"].by_prediction(prediction.prediction_id) is None


def test_repeat_restart_is_idempotent_after_reconstructed_context(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][1]
    _remove_context(runtime["context_store"], prediction.prediction_id)

    first = recover_or_reconstruct_task9_lifecycle_context(
        prediction=prediction,
        lifecycle_context_store=runtime["context_store"],
        session_policy=MarketSessionPolicy(),
    )
    second = recover_or_reconstruct_task9_lifecycle_context(
        prediction=prediction,
        lifecycle_context_store=runtime["context_store"],
        session_policy=MarketSessionPolicy(),
    )

    assert first.persistence_status == "SAVED"
    assert second.persistence_status == "EXISTING"
    assert second.context == first.context
    assert runtime["context_store"].save(first.context) == "DUPLICATE_SAME_PAYLOAD"


def test_existing_correct_context_remains_authoritative(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]
    original = runtime["context_store"].recover(prediction.prediction_id)

    result = recover_or_reconstruct_task9_lifecycle_context(
        prediction=prediction,
        lifecycle_context_store=runtime["context_store"],
        session_policy=MarketSessionPolicy(),
    )

    assert result.persistence_status == "EXISTING"
    assert result.context == original
    assert runtime["context_store"].recover(prediction.prediction_id) == original


def test_conflicting_existing_context_fails_closed_without_overwrite(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]
    expected = runtime["context_store"].recover(prediction.prediction_id)
    _remove_context(runtime["context_store"], prediction.prediction_id)
    conflicting = replace(
        expected,
        validity_window_ends_at=(
            expected.validity_window_ends_at - timedelta(seconds=1)
        ),
    )
    assert runtime["context_store"].save(conflicting) == "SAVED"

    with pytest.raises(ValueError, match="conflicting lifecycle context reconstruction"):
        recover_or_reconstruct_task9_lifecycle_context(
            prediction=prediction,
            lifecycle_context_store=runtime["context_store"],
            session_policy=MarketSessionPolicy(),
        )

    assert runtime["context_store"].recover(prediction.prediction_id) == conflicting


def test_missing_window_remains_unresolved_after_context_recovery(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][1]
    _remove_context(runtime["context_store"], prediction.prediction_id)
    quote, quality = _quote(prediction)

    assert _recover(runtime, prediction, quote, quality) == ()
    assert runtime["context_store"].recover(prediction.prediction_id) == (
        resolve_prediction_lifecycle_window(
            prediction_record=prediction,
            session_policy=MarketSessionPolicy(),
        )
    )
    assert runtime["observation_store"].recover(prediction.prediction_id) is None
    assert runtime["outcome_store"].recover(prediction.prediction_id) is None
    assert runtime["binding_store"].by_prediction(prediction.prediction_id) is None


@pytest.mark.parametrize("market,exchange", (("NIFTY", "NSE"), ("SENSEX", "BSE")))
def test_reconstruction_accepts_only_supported_task9_market_identity(tmp_path, market, exchange):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = next(
        item
        for item in runtime["predictions"]
        if (item.underlying_symbol, item.exchange) == (market, exchange)
    )
    _remove_context(runtime["context_store"], prediction.prediction_id)

    result = recover_or_reconstruct_task9_lifecycle_context(
        prediction=prediction,
        lifecycle_context_store=runtime["context_store"],
        session_policy=MarketSessionPolicy(),
    )

    assert result.context.underlying_symbol == market
    assert result.context.exchange == exchange
