"""Provider-free durable recovery tests for Task 9 WAIT/NO_TRADE evidence."""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from services.certification.task9_abstention_later_observation_recovery import finalize_task9_expired_abstentions, recover_task9_later_abstention_observations
from services.certification.task9_external_provider_blocker import Task9ExternalProviderBlockerStore
from services.contracts.prediction_lifecycle_outcome_policy_v1 import PredictionLifecycleOutcomePolicyV1
from tests.test_task916_production_child_evidence_authority import _quote, _runtime


def _policy():
    return PredictionLifecycleOutcomePolicyV1(policy_id="task926-policy", policy_version="1.0")


def _initialize(runtime, prediction):
    context = runtime["context_store"].recover(prediction.prediction_id)
    runtime["observation_store"].initialize(prediction=prediction, entry_window_ends_at=context.entry_window_ends_at, validity_window_ends_at=context.validity_window_ends_at)


def _recover(runtime, prediction, quote, quality, *, evaluated_at=None):
    return recover_task9_later_abstention_observations(
        market=prediction.underlying_symbol, exchange=prediction.exchange,
        quote=quote, data_quality=quality, prediction_ledger=runtime["ledger"],
        lifecycle_context_store=runtime["context_store"], observation_store=runtime["observation_store"],
        outcome_store=runtime["outcome_store"], outcome_policy=_policy(),
        evaluated_at=quote.observed_at if evaluated_at is None else evaluated_at,
    )


@pytest.mark.parametrize("action,market,exchange", (("WAIT", "NIFTY", "NSE"), ("NO_TRADE", "SENSEX", "BSE")))
def test_later_abstention_quote_persists_once_and_is_restart_idempotent(tmp_path, action, market, exchange):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = next(item for item in runtime["predictions"] if (item.underlying_symbol, item.exchange) == (market, exchange))
    _initialize(runtime, prediction)
    quote, quality = _quote(prediction)

    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    window = runtime["observation_store"].recover(prediction.prediction_id)
    assert len(window.observations) == 1
    assert window.observations[0].observed_at == quote.observed_at
    assert _recover(_runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE"), prediction, quote, quality) == (prediction.prediction_id,)


def test_pre_prediction_quote_is_ignored_without_timestamp_rewrite_or_outcome(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    older = replace(quote, observed_at=prediction.completed_at - timedelta(seconds=1))
    older_quality = replace(quality, observed_at=older.observed_at)
    assert _recover(runtime, prediction, older, older_quality) == ()
    assert runtime["observation_store"].recover(prediction.prediction_id).observations == ()
    assert runtime["outcome_store"].recover(prediction.prediction_id) is None


@pytest.mark.parametrize("market,exchange", (("NIFTY", "NSE"), ("SENSEX", "BSE")))
def test_expired_prior_abstention_finalizes_without_appending_current_quote(tmp_path, market, exchange):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = next(item for item in runtime["predictions"] if (item.underlying_symbol, item.exchange) == (market, exchange))
    _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    context = runtime["context_store"].recover(prediction.prediction_id)
    expired_at = context.validity_window_ends_at + timedelta(seconds=1)
    expired_quote = replace(quote, observed_at=expired_at, received_at=expired_at)
    expired_quality = replace(quality, observed_at=expired_at, received_at=expired_at)
    assert _recover(runtime, prediction, expired_quote, expired_quality) == ()
    assert runtime["observation_store"].recover(prediction.prediction_id).observations == ()
    outcome = runtime["outcome_store"].recover(prediction.prediction_id)
    assert outcome.evaluation_status == "DATA_UNAVAILABLE"
    assert outcome.outcome == "DATA_UNAVAILABLE"


@pytest.mark.parametrize(
    ("multiplier", "expected_outcome"),
    ((1.0, "NO_TRADE_CORRECT"), (1.01, "NO_TRADE_MISSED_MOVE")),
)
def test_retained_within_window_extrema_finalizes_after_window_without_append(tmp_path, multiplier, expected_outcome):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    retained_price = prediction.start_underlying_price * multiplier
    quote = replace(
        quote,
        last_price=retained_price,
        previous_close=retained_price,
        open_price=retained_price,
        high_price=retained_price,
        low_price=retained_price,
        bid_price=retained_price,
        ask_price=retained_price,
    )
    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    assert runtime["outcome_store"].recover(prediction.prediction_id) is None

    context = runtime["context_store"].recover(prediction.prediction_id)
    after_window = context.validity_window_ends_at + timedelta(seconds=1)
    current_quote = replace(quote, observed_at=after_window, received_at=after_window)
    current_quality = replace(quality, observed_at=after_window, received_at=after_window)
    assert _recover(runtime, prediction, current_quote, current_quality) == ()
    window = runtime["observation_store"].recover(prediction.prediction_id)
    assert len(window.observations) == 1
    assert window.observations[0].observed_at == quote.observed_at
    outcome = runtime["outcome_store"].recover(prediction.prediction_id)
    assert outcome.evaluation_status == "RESOLVED"
    assert outcome.outcome == expected_outcome


def test_restart_finalizes_retained_window_once_after_validity_end(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    context = runtime["context_store"].recover(prediction.prediction_id)
    after_window = context.validity_window_ends_at + timedelta(seconds=1)
    current_quote = replace(quote, observed_at=after_window, received_at=after_window)
    current_quality = replace(quality, observed_at=after_window, received_at=after_window)

    restarted = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    assert _recover(restarted, prediction, current_quote, current_quality) == ()
    outcome = restarted["outcome_store"].recover(prediction.prediction_id)
    assert outcome.evaluation_status == "RESOLVED"
    assert _recover(restarted, prediction, current_quote, current_quality) == ()
    assert len(restarted["observation_store"].recover(prediction.prediction_id).observations) == 1


def test_pre_completion_current_quote_can_finalize_retained_window_after_end(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    context = runtime["context_store"].recover(prediction.prediction_id)
    old_quote = replace(quote, observed_at=prediction.completed_at, received_at=prediction.completed_at)
    old_quality = replace(quality, observed_at=prediction.completed_at, received_at=prediction.completed_at)
    assert _recover(runtime, prediction, old_quote, old_quality, evaluated_at=context.validity_window_ends_at) == ()
    assert len(runtime["observation_store"].recover(prediction.prediction_id).observations) == 1
    assert runtime["outcome_store"].recover(prediction.prediction_id).evaluation_status == "RESOLVED"


def test_missing_window_is_not_created_during_terminal_recovery(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]
    quote, quality = _quote(prediction)
    context = runtime["context_store"].recover(prediction.prediction_id)
    after_window = context.validity_window_ends_at + timedelta(seconds=1)
    quote = replace(quote, observed_at=after_window, received_at=after_window)
    quality = replace(quality, observed_at=after_window, received_at=after_window)
    assert _recover(runtime, prediction, quote, quality) == ()
    assert runtime["observation_store"].recover(prediction.prediction_id) is None
    assert runtime["outcome_store"].recover(prediction.prediction_id) is None


@pytest.mark.parametrize("action", ("WAIT", "NO_TRADE"))
def test_provider_free_drain_finalizes_only_expired_durable_abstentions(tmp_path, action):
    runtime = _runtime(tmp_path, nifty_action=action, sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    context = runtime["context_store"].recover(prediction.prediction_id)
    finalized = finalize_task9_expired_abstentions(
        prediction_ledger=runtime["ledger"], lifecycle_context_store=runtime["context_store"],
        observation_store=runtime["observation_store"], outcome_store=runtime["outcome_store"],
        outcome_policy=_policy(), evaluated_at=context.validity_window_ends_at,
    )
    assert finalized == (prediction.prediction_id,)
    assert runtime["outcome_store"].recover(prediction.prediction_id).evaluation_status == "RESOLVED"
    assert finalize_task9_expired_abstentions(
        prediction_ledger=runtime["ledger"], lifecycle_context_store=runtime["context_store"],
        observation_store=runtime["observation_store"], outcome_store=runtime["outcome_store"],
        outcome_policy=_policy(), evaluated_at=context.validity_window_ends_at,
    ) == ()


def test_provider_free_drain_does_not_touch_unexpired_or_missing_windows(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    context = runtime["context_store"].recover(prediction.prediction_id)
    assert finalize_task9_expired_abstentions(
        prediction_ledger=runtime["ledger"], lifecycle_context_store=runtime["context_store"],
        observation_store=runtime["observation_store"], outcome_store=runtime["outcome_store"],
        outcome_policy=_policy(), evaluated_at=context.validity_window_ends_at - timedelta(seconds=1),
    ) == ()
    assert runtime["outcome_store"].recover(prediction.prediction_id) is None


def test_quote_at_validity_window_boundary_is_still_recovered(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    context = runtime["context_store"].recover(prediction.prediction_id)
    boundary = context.validity_window_ends_at
    quote = replace(quote, observed_at=boundary, received_at=boundary)
    quality = replace(quality, observed_at=boundary, received_at=boundary)
    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    assert len(runtime["observation_store"].recover(prediction.prediction_id).observations) == 1


def test_equal_or_pre_completion_quote_never_resolves_abstention_or_touches_sensex(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    nifty, sensex = runtime["predictions"]
    _initialize(runtime, nifty); _initialize(runtime, sensex)
    quote, quality = _quote(nifty)
    for observed_at in (nifty.completed_at, nifty.completed_at - timedelta(seconds=1)):
        current = replace(quote, observed_at=observed_at)
        current_quality = replace(quality, observed_at=observed_at)
        assert _recover(runtime, nifty, current, current_quality) == ()
    assert runtime["observation_store"].recover(nifty.prediction_id).observations == ()
    assert runtime["observation_store"].recover(sensex.prediction_id).observations == ()


def test_timestamp_and_market_mismatches_fail_closed(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = runtime["predictions"][0]; _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    with pytest.raises(ValueError): _recover(runtime, prediction, quote, replace(quality, observed_at=quality.observed_at + timedelta(seconds=1)))
    sensex = runtime["predictions"][1]; other_quote, other_quality = _quote(sensex)
    with pytest.raises(ValueError): _recover(runtime, prediction, other_quote, other_quality)


def test_resolved_and_call_put_predictions_are_ignored_and_blocker_is_unchanged(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="CALL", sensex_action="WAIT")
    wait = runtime["predictions"][1]; _initialize(runtime, wait)
    blocker = Task9ExternalProviderBlockerStore(tmp_path / "blocker")
    before = blocker.record("run", observed_at=wait.completed_at)
    quote, quality = _quote(wait)
    assert _recover(runtime, wait, quote, quality) == (wait.prediction_id,)
    assert blocker.load("run") == before
    assert runtime["binding_store"].by_prediction(runtime["predictions"][0].prediction_id) is None
    assert runtime["outcome_store"].recover(wait.prediction_id) is None or runtime["outcome_store"].recover(wait.prediction_id).execution_mode == "PAPER"


@pytest.mark.parametrize("market,exchange", (("NIFTY", "NSE"), ("SENSEX", "BSE")))
def test_duplicate_quote_after_restart_preserves_one_observation_and_never_creates_progress(tmp_path, monkeypatch, market, exchange):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = next(item for item in runtime["predictions"] if (item.underlying_symbol, item.exchange) == (market, exchange))
    _initialize(runtime, prediction)
    quote, quality = _quote(prediction)
    progress_path = tmp_path / "task9-progress.json"
    monkeypatch.setattr(
        "services.broker.shared_client.get_certification_market_client",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("provider call")),
    )
    assert _recover(runtime, prediction, quote, quality) == (prediction.prediction_id,)
    assert not progress_path.exists()
    restarted = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    assert _recover(restarted, prediction, quote, quality) == (prediction.prediction_id,)
    window = restarted["observation_store"].recover(prediction.prediction_id)
    assert len(window.observations) == 1
    assert not progress_path.exists()


def test_unusable_nifty_evidence_does_not_erase_valid_sensex_recovery(tmp_path):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    nifty, sensex = runtime["predictions"]
    _initialize(runtime, nifty); _initialize(runtime, sensex)
    sensex_quote, sensex_quality = _quote(sensex)
    with pytest.raises(ValueError):
        _recover(runtime, nifty, sensex_quote, sensex_quality)
    assert _recover(runtime, sensex, sensex_quote, sensex_quality) == (sensex.prediction_id,)
    assert runtime["observation_store"].recover(nifty.prediction_id).observations == ()
    assert len(runtime["observation_store"].recover(sensex.prediction_id).observations) == 1
