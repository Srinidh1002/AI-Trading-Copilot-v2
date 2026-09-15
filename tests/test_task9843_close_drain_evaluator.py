from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_close_drain_evaluator import (
    evaluate_task9_close_drain,
)
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainItemKind,
    Task9CloseDrainItemStatus,
    Task9CloseDrainItemV1,
    Task9CloseDrainStatus,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    Task9SessionPhase,
)
from services.contracts.task9_market_session_state_v1 import (
    Task9SegmentSessionStateV1,
)


IST = ZoneInfo("Asia/Kolkata")
DAY = date(2026, 8, 17)


def _state(
    segment,
    phase,
    *,
    market_date=DAY,
):
    active = phase in {
        Task9SessionPhase.OPEN,
        Task9SessionPhase.ENTRY_RESTRICTED,
    }

    return Task9SegmentSessionStateV1(
        segment=segment,
        market_date=market_date,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        timezone="Asia/Kolkata",
        phase=phase,
        market_open=active,
        new_entries_allowed=(
            phase is Task9SessionPhase.OPEN
        ),
        position_monitoring_allowed=active,
        close_drain_required=False,
        session_open_time=time(9, 15),
        new_entry_cutoff=time(15, 30),
        position_monitoring_until=time(15, 40),
        session_close_time=time(15, 40),
        calendar_status="TRADING_DAY",
        policy_id="task9843-test",
        policy_version="1",
    )


def _states(phase):
    return (
        _state(
            Task9MarketSegment.NFO_OPTIONS,
            phase,
        ),
        _state(
            Task9MarketSegment.BFO_OPTIONS,
            phase,
        ),
    )


def _item(
    prediction_id,
    *,
    market="NIFTY",
    kind=Task9CloseDrainItemKind.ABSTENTION,
    status=Task9CloseDrainItemStatus.COMPLETE,
    reasons=(),
):
    return Task9CloseDrainItemV1(
        prediction_id=prediction_id,
        market=market,
        kind=kind,
        status=status,
        reason_codes=reasons,
    )


@pytest.mark.parametrize(
    "phase",
    (
        Task9SessionPhase.PRE_OPEN,
        Task9SessionPhase.OPEN,
        Task9SessionPhase.ENTRY_RESTRICTED,
        Task9SessionPhase.NON_TRADING_DAY,
    ),
)
def test_before_both_segments_closed_drain_not_required(
    phase,
):
    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            30,
            tzinfo=IST,
        ),
        session_states=_states(phase),
        items=(),
    )

    assert result.status is Task9CloseDrainStatus.NOT_REQUIRED
    assert result.finalization_allowed is False


def test_mixed_closed_and_active_is_not_finalizable():
    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=(
            _state(
                Task9MarketSegment.NFO_OPTIONS,
                Task9SessionPhase.CLOSED,
            ),
            _state(
                Task9MarketSegment.BFO_OPTIONS,
                Task9SessionPhase.ENTRY_RESTRICTED,
            ),
        ),
        items=(),
    )

    assert result.status is Task9CloseDrainStatus.NOT_REQUIRED
    assert result.finalization_allowed is False


def test_closed_with_no_required_terminal_work_is_complete():
    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=_states(
            Task9SessionPhase.CLOSED
        ),
        items=(),
    )

    assert result.status is Task9CloseDrainStatus.COMPLETE
    assert result.finalization_allowed is True


def test_pending_abstention_blocks_finalization():
    item = _item(
        "prediction-wait",
        status=Task9CloseDrainItemStatus.PENDING,
        reasons=("ABSTENTION_VALIDITY_PENDING",),
    )

    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=_states(
            Task9SessionPhase.CLOSED
        ),
        items=(item,),
    )

    assert result.status is Task9CloseDrainStatus.PENDING
    assert result.finalization_allowed is False
    assert result.pending_prediction_ids == (
        "prediction-wait",
    )


def test_open_paper_trade_is_pending_not_fabricated_terminal():
    item = _item(
        "prediction-call",
        kind=Task9CloseDrainItemKind.PAPER_TRADE,
        status=Task9CloseDrainItemStatus.PENDING,
        reasons=("PAPER_POSITION_OPEN",),
    )

    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=_states(
            Task9SessionPhase.CLOSED
        ),
        items=(item,),
    )

    assert result.status is Task9CloseDrainStatus.PENDING
    assert result.finalization_allowed is False


def test_terminal_unreconciled_trade_is_pending():
    item = _item(
        "prediction-put",
        kind=Task9CloseDrainItemKind.PAPER_TRADE,
        status=Task9CloseDrainItemStatus.PENDING,
        reasons=("RECONCILIATION_MISSING",),
    )

    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=_states(
            Task9SessionPhase.CLOSED
        ),
        items=(item,),
    )

    assert result.status is Task9CloseDrainStatus.PENDING


def test_corrupt_state_is_blocked_and_wins_over_pending():
    items = tuple(sorted(
        (
            _item(
                "prediction-open",
                kind=Task9CloseDrainItemKind.PAPER_TRADE,
                status=Task9CloseDrainItemStatus.PENDING,
                reasons=("PAPER_POSITION_OPEN",),
            ),
            _item(
                "prediction-corrupt",
                market="SENSEX",
                kind=Task9CloseDrainItemKind.PAPER_TRADE,
                status=Task9CloseDrainItemStatus.BLOCKED,
                reasons=("BINDING_IDENTITY_MISMATCH",),
            ),
        ),
        key=lambda item: (
            item.market,
            item.prediction_id,
            item.kind.value,
        ),
    ))

    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=_states(
            Task9SessionPhase.CLOSED
        ),
        items=items,
    )

    assert result.status is Task9CloseDrainStatus.BLOCKED
    assert result.finalization_allowed is False
    assert result.blocked_prediction_ids == (
        "prediction-corrupt",
    )


def test_fully_complete_items_allow_finalization():
    items = tuple(sorted(
        (
            _item("prediction-wait"),
            _item(
                "prediction-call",
                market="SENSEX",
                kind=Task9CloseDrainItemKind.PAPER_TRADE,
            ),
        ),
        key=lambda item: (
            item.market,
            item.prediction_id,
            item.kind.value,
        ),
    ))

    result = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=_states(
            Task9SessionPhase.CLOSED
        ),
        items=items,
    )

    assert result.status is Task9CloseDrainStatus.COMPLETE
    assert result.finalization_allowed is True


def test_wrong_session_date_fails_closed():
    with pytest.raises(
        ValueError,
        match="session date mismatch",
    ):
        evaluate_task9_close_drain(
            official_run_id="run",
            market_date=DAY,
            evaluated_at=datetime(
                2026,
                8,
                17,
                15,
                40,
                tzinfo=IST,
            ),
            session_states=(
                _state(
                    Task9MarketSegment.NFO_OPTIONS,
                    Task9SessionPhase.CLOSED,
                    market_date=date(2026, 8, 18),
                ),
                _state(
                    Task9MarketSegment.BFO_OPTIONS,
                    Task9SessionPhase.CLOSED,
                ),
            ),
            items=(),
        )


def test_missing_market_session_authority_fails_closed():
    with pytest.raises(
        ValueError,
        match="exact NIFTY/SENSEX",
    ):
        evaluate_task9_close_drain(
            official_run_id="run",
            market_date=DAY,
            evaluated_at=datetime(
                2026,
                8,
                17,
                15,
                40,
                tzinfo=IST,
            ),
            session_states=(
                _state(
                    Task9MarketSegment.NFO_OPTIONS,
                    Task9SessionPhase.CLOSED,
                ),
            ),
            items=(),
        )


def test_item_contract_preserves_paper_safety():
    state = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=DAY,
        evaluated_at=datetime(
            2026,
            8,
            17,
            15,
            40,
            tzinfo=IST,
        ),
        session_states=_states(
            Task9SessionPhase.CLOSED
        ),
        items=(),
    )

    assert state.execution_mode == "PAPER"
    assert state.broker_order_submission is False
    assert state.live_execution_eligible is False
