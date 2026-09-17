from datetime import timedelta
from types import SimpleNamespace

from services.certification.task9_close_drain_facts import (
    build_task9_close_drain_items,
)
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainItemKind,
    Task9CloseDrainItemStatus,
)
from tests.test_task916_production_child_evidence_authority import (
    _runtime,
)


class _Ledger:
    def __init__(self, predictions):
        self.predictions = predictions

    def all_records(self):
        return tuple(
            prediction.to_dict()
            for prediction in self.predictions
        )


class _BindingStore:
    def __init__(self, values=None):
        self.values = values or {}

    def by_prediction(self, prediction_id):
        return self.values.get(prediction_id)


class _RecoverStore:
    def __init__(self, values=None):
        self.values = values or {}

    def recover(self, prediction_id):
        return self.values.get(prediction_id)


class _TradeService:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, trade_id):
        return self.values.get(trade_id)


def _scan(
    prediction,
    *,
    binding=None,
    window=None,
    outcome=None,
    reconciliation=None,
    snapshot=None,
    evaluated_at=None,
):
    boundary = (
        evaluated_at
        if evaluated_at is not None
        else prediction.completed_at
    )

    return build_task9_close_drain_items(
        official_run_id="task9843-run",
        market_date=prediction.completed_at.date(),
        evaluated_at=boundary,
        prediction_ledger=_Ledger((prediction,)),
        binding_store=_BindingStore(
            {}
            if binding is None
            else {
                prediction.prediction_id: binding,
            }
        ),
        observation_store=_RecoverStore(
            {}
            if window is None
            else {
                prediction.prediction_id: window,
            }
        ),
        outcome_store=_RecoverStore(
            {}
            if outcome is None
            else {
                prediction.prediction_id: outcome,
            }
        ),
        reconciliation_store=_RecoverStore(
            {}
            if reconciliation is None
            else {
                prediction.prediction_id:
                    reconciliation,
            }
        ),
        trade_persistence_service=_TradeService(
            {}
            if snapshot is None
            else {
                binding.paper_trade_id: snapshot,
            }
        ),
    )


def _abstention_prediction(tmp_path, action):
    runtime = _runtime(
        tmp_path,
        nifty_action=action,
        sensex_action="NO_TRADE",
    )
    return runtime, runtime["predictions"][0]


def test_abstention_with_terminal_outcome_is_complete(
    tmp_path,
):
    runtime, prediction = _abstention_prediction(
        tmp_path,
        "WAIT",
    )

    outcome = SimpleNamespace(
        prediction_id=prediction.prediction_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
    )

    items = _scan(
        prediction,
        outcome=outcome,
    )

    assert len(items) == 1
    assert (
        items[0].kind
        is Task9CloseDrainItemKind.ABSTENTION
    )
    assert (
        items[0].status
        is Task9CloseDrainItemStatus.COMPLETE
    )


def test_unexpired_abstention_is_pending(tmp_path):
    runtime, prediction = _abstention_prediction(
        tmp_path,
        "WAIT",
    )
    context = runtime["context_store"].recover(
        prediction.prediction_id
    )

    window = SimpleNamespace(
        prediction_id=prediction.prediction_id,
        validity_window_ends_at=(
            context.validity_window_ends_at
        ),
    )

    items = _scan(
        prediction,
        window=window,
        evaluated_at=prediction.completed_at,
    )

    assert (
        items[0].status
        is Task9CloseDrainItemStatus.PENDING
    )
    assert items[0].reason_codes == (
        "ABSTENTION_VALIDITY_PENDING",
    )


def test_expired_abstention_without_outcome_is_blocked(
    tmp_path,
):
    runtime, prediction = _abstention_prediction(
        tmp_path,
        "NO_TRADE",
    )
    context = runtime["context_store"].recover(
        prediction.prediction_id
    )

    window = SimpleNamespace(
        prediction_id=prediction.prediction_id,
        validity_window_ends_at=(
            context.validity_window_ends_at
        ),
    )

    items = _scan(
        prediction,
        window=window,
        evaluated_at=(
            context.validity_window_ends_at
            + timedelta(seconds=1)
        ),
    )

    assert (
        items[0].status
        is Task9CloseDrainItemStatus.BLOCKED
    )
    assert items[0].reason_codes == (
        "EXPIRED_ABSTENTION_OUTCOME_MISSING",
    )


def test_missing_abstention_window_is_fail_visible(
    tmp_path,
):
    _, prediction = _abstention_prediction(
        tmp_path,
        "WAIT",
    )

    items = _scan(prediction)

    assert (
        items[0].status
        is Task9CloseDrainItemStatus.BLOCKED
    )
    assert items[0].reason_codes == (
        "ABSTENTION_WINDOW_MISSING",
    )


def _directional_prediction(tmp_path):
    runtime = _runtime(
        tmp_path,
        nifty_action="CALL",
        sensex_action="NO_TRADE",
    )
    return runtime, runtime["predictions"][0]


def _binding(prediction):
    return SimpleNamespace(
        official_run_id="task9843-run",
        prediction_id=prediction.prediction_id,
        market=prediction.underlying_symbol,
        underlying_exchange=prediction.exchange,
        paper_trade_id="paper-trade-1",
        paper_position_id="paper-position-1",
        entered_at=prediction.completed_at,
    )


def _snapshot(binding, *, terminal):
    return SimpleNamespace(
        paper_trade_id=binding.paper_trade_id,
        position=SimpleNamespace(
            position_id=binding.paper_position_id,
        ),
        lifecycle_state=SimpleNamespace(
            is_terminal=terminal,
        ),
    )


def test_unbound_directional_prediction_has_no_trade_to_drain(
    tmp_path,
):
    _, prediction = _directional_prediction(
        tmp_path
    )

    assert _scan(prediction) == ()


def test_open_bound_paper_position_remains_pending(
    tmp_path,
):
    _, prediction = _directional_prediction(
        tmp_path
    )
    binding = _binding(prediction)

    items = _scan(
        prediction,
        binding=binding,
        snapshot=_snapshot(
            binding,
            terminal=False,
        ),
    )

    assert (
        items[0].kind
        is Task9CloseDrainItemKind.PAPER_TRADE
    )
    assert (
        items[0].status
        is Task9CloseDrainItemStatus.PENDING
    )
    assert items[0].reason_codes == (
        "PAPER_POSITION_OPEN",
    )


def test_terminal_trade_without_outcome_is_pending(
    tmp_path,
):
    _, prediction = _directional_prediction(
        tmp_path
    )
    binding = _binding(prediction)

    items = _scan(
        prediction,
        binding=binding,
        snapshot=_snapshot(
            binding,
            terminal=True,
        ),
    )

    assert (
        items[0].status
        is Task9CloseDrainItemStatus.PENDING
    )
    assert items[0].reason_codes == (
        "LIFECYCLE_OUTCOME_MISSING",
    )


def test_terminal_trade_without_reconciliation_is_pending(
    tmp_path,
):
    _, prediction = _directional_prediction(
        tmp_path
    )
    binding = _binding(prediction)
    outcome = SimpleNamespace(
        outcome_id="outcome-1",
        prediction_id=prediction.prediction_id,
    )

    items = _scan(
        prediction,
        binding=binding,
        snapshot=_snapshot(
            binding,
            terminal=True,
        ),
        outcome=outcome,
    )

    assert (
        items[0].status
        is Task9CloseDrainItemStatus.PENDING
    )
    assert items[0].reason_codes == (
        "RECONCILIATION_MISSING",
    )


def test_fully_reconciled_terminal_trade_is_complete(
    tmp_path,
):
    _, prediction = _directional_prediction(
        tmp_path
    )
    binding = _binding(prediction)
    outcome = SimpleNamespace(
        outcome_id="outcome-1",
        prediction_id=prediction.prediction_id,
    )
    reconciliation = SimpleNamespace(
        prediction_id=prediction.prediction_id,
        underlying_symbol=prediction.underlying_symbol,
        exchange=prediction.exchange,
        predicted_action=prediction.predicted_action,
        position_id=binding.paper_position_id,
        lifecycle_outcome_id=outcome.outcome_id,
        status="RECONCILED",
        reconciliation_complete=True,
        identity_matches=True,
    )

    items = _scan(
        prediction,
        binding=binding,
        snapshot=_snapshot(
            binding,
            terminal=True,
        ),
        outcome=outcome,
        reconciliation=reconciliation,
    )

    assert (
        items[0].status
        is Task9CloseDrainItemStatus.COMPLETE
    )
    assert items[0].reason_codes == ()


def test_corrupt_binding_identity_is_blocked(tmp_path):
    _, prediction = _directional_prediction(
        tmp_path
    )
    binding = _binding(prediction)
    binding = SimpleNamespace(
        **{
            **binding.__dict__,
            "official_run_id": "wrong-run",
        }
    )

    items = _scan(
        prediction,
        binding=binding,
    )

    assert (
        items[0].status
        is Task9CloseDrainItemStatus.BLOCKED
    )
    assert items[0].reason_codes == (
        "BINDING_IDENTITY_MISMATCH",
    )
