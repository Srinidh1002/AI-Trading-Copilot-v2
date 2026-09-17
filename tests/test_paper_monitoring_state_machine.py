"""Task 5 Slice 5 monitoring lifecycle state-machine certification."""
from datetime import datetime, timedelta, timezone

import pytest

from services.contracts.active_paper_position_v1 import ActivePaperPositionV1
from services.contracts.paper_monitoring_lifecycle_v1 import PaperMonitoringEvidenceV1
from services.paper_trading.paper_monitoring_state_machine import (
    evaluate_paper_position_lifecycle,
)

NOW = datetime(2026, 8, 3, 9, 45, tzinfo=timezone.utc)


def position(**changes):
    values = dict(
        position_id="position-1",
        recommendation_id="recommendation-1",
        reservation_result_id="reservation-1",
        fill_result_id="fill-1",
        opened_at=NOW - timedelta(minutes=5),
        updated_at=NOW - timedelta(seconds=1),
        underlying_symbol="NIFTY",
        exchange="NSE",
        option_right="CALL",
        contract="NIFTY06AUG26C25000",
        expiry="2026-08-06",
        strike=25000.0,
        entry_price=100.0,
        stop_loss=90.0,
        target_1=110.0,
        target_2=120.0,
        target_3=130.0,
        initial_lots=3,
        remaining_lots=3,
        lot_size=25,
        initial_quantity=75,
        remaining_quantity=75,
        reserved_capital=7600.0,
        maximum_loss=1000.0,
    )
    values.update(changes)
    return ActivePaperPositionV1(**values)


def evidence(**changes):
    values = dict(
        evidence_id="evidence-1",
        position_id="position-1",
        observed_at=NOW,
        current_bid=105.0,
        current_ask=106.0,
        current_last=105.5,
        confidence=0.8,
        setup_valid=True,
    )
    values.update(changes)
    return PaperMonitoringEvidenceV1(**values)


def evaluate(p=None, e=None):
    return evaluate_paper_position_lifecycle(
        transition_id="transition-1",
        position=p or position(),
        evidence=e or evidence(),
    )


def test_valid_setup_holds():
    result = evaluate()
    assert result.action == "HOLD"
    assert result.remaining_quantity == 75


def test_low_confidence_holds_with_caution():
    result = evaluate(e=evidence(confidence=0.4))
    assert result.action == "HOLD_WITH_CAUTION"
    assert "CONFIDENCE_DETERIORATED" in result.reasons


def test_contradictions_hold_with_caution():
    result = evaluate(e=evidence(contradictions=("TREND_OPTION_CONFLICT",)))
    assert result.action == "HOLD_WITH_CAUTION"


def test_target_one_partial_exit():
    result = evaluate(e=evidence(current_bid=110.0, current_ask=111.0, current_last=110.5))
    assert result.action == "TARGET_1_HIT"
    assert result.exit_quantity == 25
    assert result.remaining_quantity == 50
    assert result.next_state == "PARTIALLY_EXITED"


def test_target_two_partial_exit():
    p = position(
        lifecycle_state="PARTIALLY_EXITED",
        remaining_lots=2,
        remaining_quantity=50,
        target_1_hit=True,
    )
    result = evaluate(
        p=p,
        e=evidence(current_bid=120.0, current_ask=121.0, current_last=120.5),
    )
    assert result.action == "TARGET_2_HIT"
    assert result.exit_quantity == 25
    assert result.remaining_quantity == 25


def test_target_three_closes_remaining_position():
    p = position(
        lifecycle_state="PARTIALLY_EXITED",
        remaining_lots=1,
        remaining_quantity=25,
        target_1_hit=True,
        target_2_hit=True,
    )
    result = evaluate(
        p=p,
        e=evidence(current_bid=130.0, current_ask=131.0, current_last=130.5),
    )
    assert result.action == "TARGET_3_HIT"
    assert result.next_state == "CLOSED"
    assert result.remaining_quantity == 0


def test_stop_hit_has_priority():
    result = evaluate(
        e=evidence(
            current_bid=89.0,
            current_ask=90.0,
            current_last=89.5,
            confidence=0.9,
        )
    )
    assert result.action == "STOP_HIT"
    assert result.next_state == "CLOSED"


def test_safety_exit_and_invalidated_setup_exit_now():
    assert evaluate(e=evidence(safety_exit_required=True)).action == "EXIT_NOW"
    assert evaluate(e=evidence(setup_valid=False)).action == "EXIT_NOW"


def test_stale_evidence_never_exits_or_targets():
    result = evaluate(
        e=evidence(
            current_bid=140.0,
            current_ask=141.0,
            current_last=140.5,
            is_stale=True,
        )
    )
    assert result.action == "HOLD_WITH_CAUTION"
    assert result.exit_quantity == 0


def test_mismatched_or_old_evidence_rejected():
    with pytest.raises(ValueError, match="mismatch"):
        evaluate(e=evidence(position_id="position-2"))
    with pytest.raises(ValueError, match="precedes"):
        evaluate(e=evidence(observed_at=NOW - timedelta(seconds=2)))
