"""Task 9.95A deterministic restart-recovery dispatcher coverage.

This file intentionally tests the dispatcher before launcher/startup wiring.
It reuses the exact typed Task 9.93 P7/P8 transactional-recovery fixtures.
"""

from dataclasses import replace

import pytest

from services.certification.task9_pending_entry_store import (
    Task9PendingEntryStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
    Task9PredictionPaperTradeBindingV1,
)
from services.certification.task9_restart_recovery_dispatcher import (
    Task9RestartRecoveryDispatcher,
)
from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
    execute_admitted_plan_simulated_entry,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)

from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)
from tests.test_task993_entry_binding_transactional_recovery import (
    _crashed_after_p7,
    _pending,
    _serializable_entry,
)


class _OnePredictionLedger:
    """Minimal read seam only; execution persistence remains real P7/P8."""

    def __init__(self, prediction):
        self.prediction = prediction

    def recover(self, prediction_id):
        if prediction_id == self.prediction.prediction_id:
            return self.prediction
        return None


class _RecoverStore:
    """Small read seam for downstream facts not under test in 9.95A."""

    def __init__(self, value=None):
        self.value = value

    def recover(self, prediction_id):
        return self.value


class _UnusedStore:
    pass


def _prediction_for(entry, *, action="CALL"):
    """Create only the dispatcher-facing durable prediction identity.

    The dispatcher reads prediction_id and predicted_action for these
    executed-position tests. No execution fact is constructed here.
    """
    return type(
        "DurablePredictionForDispatcherTest",
        (),
        {
            "prediction_id": entry.prediction_id,
            "predicted_action": action,
        },
    )()


def _dispatcher(
    *,
    entry,
    portfolios,
    trades,
    pending_store,
    binding_store,
    outcome=None,
    reconciliation=None,
    terminal_recovery=None,
):
    return Task9RestartRecoveryDispatcher(
        official_run_id="task995-run",
        prediction_ledger=_OnePredictionLedger(
            _prediction_for(entry)
        ),
        lifecycle_context_store=_UnusedStore(),
        observation_store=_UnusedStore(),
        pending_entry_store=pending_store,
        binding_store=binding_store,
        outcome_store=_RecoverStore(outcome),
        reconciliation_store=_RecoverStore(reconciliation),
        trade_persistence_service=trades,
        portfolio_persistence_service=portfolios,
        terminal_recovery=terminal_recovery,
    )


def _assert_paper_only(result):
    assert result.execution_mode == "PAPER"
    assert result.broker_order_submission is False
    assert result.live_execution_eligible is False


def test_pending_entry_without_p7_is_entry_pending(tmp_path):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(args, "task995-entry-pending")

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )

    pending_store.save(_pending(entry))

    result = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    ).recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    assert result.status == "ENTRY_PENDING"
    assert trades.get(entry.paper_trade_id) is None
    assert binding_store.by_prediction(entry.prediction_id) is None
    assert (
        pending_store.recover(entry.prediction_id).status
        == "WAITING_FOR_ENTRY"
    )
    _assert_paper_only(result)


def test_p7_open_p8_pending_binding_missing_is_recovered(
    tmp_path,
    monkeypatch,
):
    entry, portfolios, trades = _crashed_after_p7(
        tmp_path,
        monkeypatch,
    )

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )
    pending_store.save(_pending(entry))

    before = portfolios.get(entry.portfolio_id)
    assert (
        before.portfolio_snapshot.reservations[0].reservation_status
        == "PENDING_HOLD"
    )

    result = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    ).recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    after = portfolios.get(entry.portfolio_id)
    binding = binding_store.by_prediction(entry.prediction_id)

    assert result.status == "RECOVERED"
    assert binding is not None
    assert binding.paper_trade_id == entry.paper_trade_id
    assert binding.paper_position_id == entry.position_id
    assert (
        after.portfolio_snapshot.reservations[0].reservation_status
        == "ACTIVE"
    )
    assert len(after.portfolio_snapshot.position_references) == 1
    assert pending_store.recover(entry.prediction_id).status == "OPEN"
    _assert_paper_only(result)


def test_p7_open_p8_active_binding_missing_is_recovered_without_economic_change(
    tmp_path,
):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(
        args,
        "task995-active-binding-missing",
    )

    execute_admitted_plan_simulated_entry(**args)

    p7_before = trades.get(entry.paper_trade_id)
    p8_before = portfolios.get(entry.portfolio_id)

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )
    pending_store.save(_pending(entry))

    result = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    ).recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    assert result.status == "RECOVERED"
    assert trades.get(entry.paper_trade_id) == p7_before
    assert portfolios.get(entry.portfolio_id) == p8_before

    binding = binding_store.by_prediction(entry.prediction_id)
    assert binding is not None
    assert binding.paper_trade_id == entry.paper_trade_id
    assert binding.paper_position_id == entry.position_id
    _assert_paper_only(result)


def test_recovered_orphan_replay_is_idempotent(
    tmp_path,
    monkeypatch,
):
    entry, portfolios, trades = _crashed_after_p7(
        tmp_path,
        monkeypatch,
    )

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )
    pending_store.save(_pending(entry))

    dispatcher = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    )

    first = dispatcher.recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    p7_after_first = trades.get(entry.paper_trade_id)
    p8_after_first = portfolios.get(entry.portfolio_id)
    binding_after_first = binding_store.by_prediction(
        entry.prediction_id
    )

    second = dispatcher.recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    assert first.status == "RECOVERED"

    # Once pending state is OPEN, the dispatcher should classify the
    # durable active position rather than replay entry again.
    assert second.status == "POSITION_ACTIVE"

    assert trades.get(entry.paper_trade_id) == p7_after_first
    assert portfolios.get(entry.portfolio_id) == p8_after_first
    assert (
        binding_store.by_prediction(entry.prediction_id)
        == binding_after_first
    )
    assert len(
        p8_after_first.portfolio_snapshot.position_references
    ) == 1
    _assert_paper_only(first)
    _assert_paper_only(second)


def test_valid_open_position_is_classified_active_without_entry_replay(
    tmp_path,
):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(args, "task995-open")

    execute_admitted_plan_simulated_entry(**args)

    snapshot = trades.get(entry.paper_trade_id)
    assert snapshot.lifecycle_state.current_state == "OPEN"

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )

    position = snapshot.position
    assert position is not None

    binding_store.save(
        Task9PredictionPaperTradeBindingV1(
            official_run_id="task995-run",
            prediction_id=entry.prediction_id,
            market=position.underlying_symbol,
            paper_trade_id=snapshot.paper_trade_id,
            paper_position_id=position.position_id,
            option_symbol=position.option_symbol,
            entered_at=position.opened_at,
        )
    )

    p7_before = trades.get(entry.paper_trade_id)
    p8_before = portfolios.get(entry.portfolio_id)

    result = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    ).recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    assert result.status == "POSITION_ACTIVE"
    assert result.detail == "OPEN"
    assert trades.get(entry.paper_trade_id) == p7_before
    assert portfolios.get(entry.portfolio_id) == p8_before
    _assert_paper_only(result)


def test_binding_to_unknown_trade_fails_closed(tmp_path):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(args, "task995-unknown-trade")

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )

    binding_store.save(
        Task9PredictionPaperTradeBindingV1(
            official_run_id="task995-run",
            prediction_id=entry.prediction_id,
            market=entry.observation.market,
            paper_trade_id="missing-paper-trade",
            paper_position_id=entry.position_id,
            option_symbol=entry.observation.option_symbol,
            entered_at=entry.evaluated_at,
        )
    )

    result = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    ).recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    assert result.status == "BLOCKED_CORRUPT_STATE"
    assert "unknown P7 trade" in result.detail
    _assert_paper_only(result)


@pytest.mark.parametrize(
    "field,bad_value",
    (
        ("market", "SENSEX"),
        ("paper_position_id", "wrong-position"),
        ("option_symbol", "WRONGOPTION"),
    ),
)
def test_binding_identity_mismatch_fails_closed(
    tmp_path,
    field,
    bad_value,
):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(
        args,
        f"task995-binding-mismatch-{field}",
    )

    execute_admitted_plan_simulated_entry(**args)

    snapshot = trades.get(entry.paper_trade_id)
    position = snapshot.position
    assert position is not None

    values = dict(
        official_run_id="task995-run",
        prediction_id=entry.prediction_id,
        market=position.underlying_symbol,
        paper_trade_id=snapshot.paper_trade_id,
        paper_position_id=position.position_id,
        option_symbol=position.option_symbol,
        entered_at=position.opened_at,
    )
    values[field] = bad_value

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )
    binding_store.save(Task9PredictionPaperTradeBindingV1(**values))

    result = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    ).recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    assert result.status == "BLOCKED_CORRUPT_STATE"
    _assert_paper_only(result)


def test_missing_binding_without_terminal_facts_is_publication_incomplete(
    tmp_path,
):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(
        args,
        "task995-publication-incomplete",
    )

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )

    result = _dispatcher(
        entry=entry,
        portfolios=portfolios,
        trades=trades,
        pending_store=pending_store,
        binding_store=binding_store,
    ).recover(
        prediction_id=entry.prediction_id,
        evaluated_at=entry.evaluated_at,
    )

    assert result.status == "PUBLICATION_INCOMPLETE"
    assert result.detail == "binding unavailable"
    _assert_paper_only(result)


def test_missing_prediction_fails_closed(tmp_path):
    args, portfolios, trades = _admitted_runtime_args(tmp_path)
    entry = _serializable_entry(args, "task995-missing-prediction")

    pending_store = Task9PendingEntryStore(
        tmp_path / "pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "bindings.json"
    )

    dispatcher = Task9RestartRecoveryDispatcher(
        official_run_id="task995-run",
        prediction_ledger=_OnePredictionLedger(
            _prediction_for(entry)
        ),
        lifecycle_context_store=_UnusedStore(),
        observation_store=_UnusedStore(),
        pending_entry_store=pending_store,
        binding_store=binding_store,
        outcome_store=_RecoverStore(),
        reconciliation_store=_RecoverStore(),
        trade_persistence_service=trades,
        portfolio_persistence_service=portfolios,
    )

    result = dispatcher.recover(
        prediction_id="different-prediction",
        evaluated_at=entry.evaluated_at,
    )

    assert result.status == "BLOCKED_CORRUPT_STATE"
    assert "prediction missing" in result.detail
    _assert_paper_only(result)

# ---------------------------------------------------------------------------
# Task 9.95A — abstention / lifecycle-side dispatcher coverage
# ---------------------------------------------------------------------------

from services.certification.task9_prediction_lifecycle_reconciliation_store import (
    Task9PredictionLifecycleReconciliationStore,
)
from services.prediction_outcomes.prediction_lifecycle_reconciliation_service import (
    reconcile_prediction_lifecycle,
)
from tests.test_r78_prediction_lifecycle_reconciliation_service import (
    lifecycle_outcome as _r78_lifecycle_outcome,
)
from tests.test_task916_production_child_evidence_authority import (
    _runtime as _task916_prediction_runtime,
)


def _task995_abstention_runtime(
    tmp_path,
    *,
    action,
    market,
    exchange,
):
    runtime = _task916_prediction_runtime(
        tmp_path,
        nifty_action=(
            action
            if (market, exchange) == ("NIFTY", "NSE")
            else "WAIT"
        ),
        sensex_action=(
            action
            if (market, exchange) == ("SENSEX", "BSE")
            else "NO_TRADE"
        ),
    )

    prediction = next(
        item
        for item in runtime["predictions"]
        if (
            item.underlying_symbol,
            item.exchange,
        )
        == (market, exchange)
    )

    assert prediction.predicted_action == action

    pending_store = Task9PendingEntryStore(
        tmp_path / "task995-abstention-pending.json"
    )
    binding_store = Task9PredictionPaperTradeBindingStore(
        tmp_path / "task995-abstention-bindings.json"
    )
    reconciliation_store = (
        Task9PredictionLifecycleReconciliationStore(
            tmp_path / "task995-abstention-reconciliation.json"
        )
    )

    dispatcher = Task9RestartRecoveryDispatcher(
        official_run_id="task995-run",
        prediction_ledger=runtime["ledger"],
        lifecycle_context_store=runtime["context_store"],
        observation_store=runtime["observation_store"],
        pending_entry_store=pending_store,
        binding_store=binding_store,
        outcome_store=runtime["outcome_store"],
        reconciliation_store=reconciliation_store,
        trade_persistence_service=_UnusedStore(),
        portfolio_persistence_service=_UnusedStore(),
    )

    return (
        runtime,
        prediction,
        pending_store,
        binding_store,
        reconciliation_store,
        dispatcher,
    )


@pytest.mark.parametrize(
    "action,market,exchange",
    (
        ("WAIT", "NIFTY", "NSE"),
        ("NO_TRADE", "SENSEX", "BSE"),
    ),
)
def test_abstention_without_terminal_outcome_is_pending_observation(
    tmp_path,
    action,
    market,
    exchange,
):
    (
        runtime,
        prediction,
        pending_store,
        binding_store,
        reconciliation_store,
        dispatcher,
    ) = _task995_abstention_runtime(
        tmp_path,
        action=action,
        market=market,
        exchange=exchange,
    )

    assert pending_store.recover(prediction.prediction_id) is None
    assert binding_store.by_prediction(prediction.prediction_id) is None
    assert runtime["outcome_store"].recover(
        prediction.prediction_id
    ) is None
    assert reconciliation_store.recover(
        prediction.prediction_id
    ) is None

    result = dispatcher.recover(
        prediction_id=prediction.prediction_id,
        evaluated_at=prediction.completed_at,
    )

    assert result.status == "ABSTENTION_PENDING_OBSERVATION"

    # Dispatcher may reconstruct/persist lifecycle context, but must not
    # create execution facts or synthesize an outcome.
    assert runtime["context_store"].recover(
        prediction.prediction_id
    ) is not None
    assert pending_store.recover(prediction.prediction_id) is None
    assert binding_store.by_prediction(prediction.prediction_id) is None
    assert runtime["outcome_store"].recover(
        prediction.prediction_id
    ) is None
    assert reconciliation_store.recover(
        prediction.prediction_id
    ) is None

    _assert_paper_only(result)


@pytest.mark.parametrize(
    "action,market,exchange",
    (
        ("WAIT", "NIFTY", "NSE"),
        ("NO_TRADE", "SENSEX", "BSE"),
    ),
)
def test_abstention_dispatcher_replay_is_idempotent(
    tmp_path,
    action,
    market,
    exchange,
):
    (
        runtime,
        prediction,
        pending_store,
        binding_store,
        reconciliation_store,
        dispatcher,
    ) = _task995_abstention_runtime(
        tmp_path,
        action=action,
        market=market,
        exchange=exchange,
    )

    first = dispatcher.recover(
        prediction_id=prediction.prediction_id,
        evaluated_at=prediction.completed_at,
    )

    context_after_first = runtime["context_store"].recover(
        prediction.prediction_id
    )

    second = dispatcher.recover(
        prediction_id=prediction.prediction_id,
        evaluated_at=prediction.completed_at,
    )

    assert first.status == "ABSTENTION_PENDING_OBSERVATION"
    assert second.status == "ABSTENTION_PENDING_OBSERVATION"

    assert (
        runtime["context_store"].recover(prediction.prediction_id)
        == context_after_first
    )
    assert pending_store.recover(prediction.prediction_id) is None
    assert binding_store.by_prediction(prediction.prediction_id) is None
    assert runtime["outcome_store"].recover(
        prediction.prediction_id
    ) is None
    assert reconciliation_store.recover(
        prediction.prediction_id
    ) is None

    _assert_paper_only(first)
    _assert_paper_only(second)


@pytest.mark.parametrize(
    "action,market,exchange",
    (
        ("WAIT", "NIFTY", "NSE"),
        ("NO_TRADE", "SENSEX", "BSE"),
    ),
)
def test_abstention_with_execution_binding_fails_closed(
    tmp_path,
    action,
    market,
    exchange,
):
    (
        runtime,
        prediction,
        pending_store,
        binding_store,
        reconciliation_store,
        dispatcher,
    ) = _task995_abstention_runtime(
        tmp_path,
        action=action,
        market=market,
        exchange=exchange,
    )

    binding_store.save(
        Task9PredictionPaperTradeBindingV1(
            official_run_id="task995-run",
            prediction_id=prediction.prediction_id,
            market=prediction.underlying_symbol,
            paper_trade_id="illegal-abstention-trade",
            paper_position_id="illegal-abstention-position",
            option_symbol="ILLEGALOPTION",
            entered_at=prediction.completed_at,
        )
    )

    result = dispatcher.recover(
        prediction_id=prediction.prediction_id,
        evaluated_at=prediction.completed_at,
    )

    assert result.status == "BLOCKED_CORRUPT_STATE"
    assert "abstention has executed lifecycle state" in result.detail

    # No attempt to inspect/fabricate the nonexistent P7 should occur.
    assert pending_store.recover(prediction.prediction_id) is None
    assert runtime["outcome_store"].recover(
        prediction.prediction_id
    ) is None
    assert reconciliation_store.recover(
        prediction.prediction_id
    ) is None

    _assert_paper_only(result)


@pytest.mark.parametrize(
    "action,market,exchange",
    (
        ("WAIT", "NIFTY", "NSE"),
        ("NO_TRADE", "SENSEX", "BSE"),
    ),
)
def test_completed_abstention_is_already_complete(
    tmp_path,
    action,
    market,
    exchange,
):
    (
        runtime,
        prediction,
        pending_store,
        binding_store,
        reconciliation_store,
        dispatcher,
    ) = _task995_abstention_runtime(
        tmp_path,
        action=action,
        market=market,
        exchange=exchange,
    )

    outcome = _r78_lifecycle_outcome(
        prediction,
        outcome="NO_TRADE_CORRECT",
        evaluation_status="RESOLVED",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type="VALIDITY_WINDOW_END",
        terminal_event_at=prediction.completed_at,
        terminal_option_premium=None,
    )

    assert runtime["outcome_store"].save(outcome) == "SAVED"

    reconciliation = reconcile_prediction_lifecycle(
        prediction=prediction,
        outcome=outcome,
        position=None,
        reconciled_at=prediction.completed_at,
    )

    assert reconciliation.status == "RECONCILED"
    assert reconciliation.position_id is None

    assert (
        reconciliation_store.save(reconciliation)
        == "SAVED"
    )

    result = dispatcher.recover(
        prediction_id=prediction.prediction_id,
        evaluated_at=prediction.completed_at,
    )

    assert result.status == "ALREADY_COMPLETE"
    assert result.detail == "abstention complete"

    assert pending_store.recover(prediction.prediction_id) is None
    assert binding_store.by_prediction(prediction.prediction_id) is None

    _assert_paper_only(result)


@pytest.mark.parametrize(
    "missing_side",
    ("OUTCOME", "RECONCILIATION"),
)
def test_abstention_partial_terminal_publication_remains_pending(
    tmp_path,
    missing_side,
):
    (
        runtime,
        prediction,
        pending_store,
        binding_store,
        reconciliation_store,
        dispatcher,
    ) = _task995_abstention_runtime(
        tmp_path,
        action="WAIT",
        market="NIFTY",
        exchange="NSE",
    )

    outcome = _r78_lifecycle_outcome(
        prediction,
        outcome="NO_TRADE_CORRECT",
        evaluation_status="RESOLVED",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type="VALIDITY_WINDOW_END",
        terminal_event_at=prediction.completed_at,
        terminal_option_premium=None,
    )

    reconciliation = reconcile_prediction_lifecycle(
        prediction=prediction,
        outcome=outcome,
        position=None,
        reconciled_at=prediction.completed_at,
    )

    if missing_side == "RECONCILIATION":
        assert runtime["outcome_store"].save(outcome) == "SAVED"
    else:
        assert (
            reconciliation_store.save(reconciliation)
            == "SAVED"
        )

    result = dispatcher.recover(
        prediction_id=prediction.prediction_id,
        evaluated_at=prediction.completed_at,
    )

    # Current dispatcher requires both downstream facts to declare complete.
    # It does not invent the missing durable fact.
    assert result.status == "ABSTENTION_PENDING_OBSERVATION"

    assert pending_store.recover(prediction.prediction_id) is None
    assert binding_store.by_prediction(prediction.prediction_id) is None

    _assert_paper_only(result)
