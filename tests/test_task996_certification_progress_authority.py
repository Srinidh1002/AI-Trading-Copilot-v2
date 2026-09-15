"""Task 9.96 canonical certification progress completeness."""

from __future__ import annotations

from copy import deepcopy

import pytest

from services.certification.task9_live_paper_certification_progress_builder import (
    build_task9_live_paper_certification_progress_from_raw,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)


def _fact(
    prediction_id,
    *,
    market,
    action,
    counting_status,
    officially_counted=False,
    entry_occurred=False,
    closed_position=False,
    lifecycle_status="RESOLVED",
    reconciliation_status="RECONCILED",
    outcome="NO_TRADE_CORRECT",
):
    return {
        "prediction_id": prediction_id,
        "market": market,
        "action": action,
        "counting_status": counting_status,
        "officially_counted": officially_counted,
        "entry_occurred": entry_occurred,
        "closed_position": closed_position,
        "lifecycle_status": lifecycle_status,
        "reconciliation_status": reconciliation_status,
        "outcome": outcome,
    }


def _report(
    *,
    session_date="2026-08-18",
    facts=(),
    excluded=(),
    unresolved=(),
    incidents=(),
    duplicates=(),
):
    return {
        "schema_version": "paper_certification_daily_report.v1",
        "report_status": "RECONCILED",
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
        "broker_order_submission": False,
        "read_only": True,
        "session_date": session_date,
        "prediction_facts": list(facts),
        "excluded_audit": list(excluded),
        "unresolved_audit": list(unresolved),
        "incidents": list(incidents),
        "duplicate_attempts": list(duplicates),
    }


def _progress(*reports):
    return build_task9_live_paper_certification_progress_from_raw(
        tuple(reports)
    )


def test_only_closed_reconciled_entered_directional_trade_counts():
    facts = (
        _fact(
            "nifty-counted",
            market="NIFTY",
            action="CALL",
            counting_status="INCLUDED",
            officially_counted=True,
            entry_occurred=True,
            closed_position=True,
        ),
        _fact(
            "nifty-open",
            market="NIFTY",
            action="PUT",
            counting_status="PENDING_OUTCOME",
            entry_occurred=True,
            closed_position=False,
            lifecycle_status="PENDING",
            reconciliation_status="PENDING",
            outcome="PENDING",
        ),
        _fact(
            "sensex-not-entered",
            market="SENSEX",
            action="CALL",
            counting_status="EXCLUDED_NO_ENTRY",
            officially_counted=False,
            entry_occurred=False,
            closed_position=False,
        ),
        _fact(
            "sensex-closed-not-reconciled",
            market="SENSEX",
            action="PUT",
            counting_status="PENDING_OUTCOME",
            officially_counted=False,
            entry_occurred=True,
            closed_position=True,
            lifecycle_status="RESOLVED",
            reconciliation_status="PENDING",
            outcome="T1_HIT",
        ),
    )

    progress = _progress(
        _report(facts=facts)
    )

    assert progress.nifty.completed_live_paper_trades == 1
    assert progress.nifty.pending_entered_trades == 1
    assert progress.nifty.remaining_trade_count == 99

    assert progress.sensex.completed_live_paper_trades == 0
    assert progress.sensex.pending_entered_trades == 0
    assert progress.sensex.remaining_trade_count == 100


@pytest.mark.parametrize(
    (
        "action",
        "counting_status",
        "outcome",
        "completed_field",
        "passed_field",
        "failed_field",
    ),
    (
        (
            "NO_TRADE",
            "INCLUDED_NON_TRADE",
            "NO_TRADE_CORRECT",
            "no_trade_completed",
            "no_trade_passed",
            "no_trade_failed",
        ),
        (
            "NO_TRADE",
            "INCLUDED_NON_TRADE",
            "NO_TRADE_MISSED_MOVE",
            "no_trade_completed",
            "no_trade_passed",
            "no_trade_failed",
        ),
        (
            "WAIT",
            "INCLUDED_WAIT",
            "NO_TRADE_CORRECT",
            "wait_completed",
            "wait_passed",
            "wait_failed",
        ),
        (
            "WAIT",
            "INCLUDED_WAIT",
            "NO_TRADE_MISSED_MOVE",
            "wait_completed",
            "wait_passed",
            "wait_failed",
        ),
    ),
)
def test_resolved_abstentions_are_separate_and_never_increment_trade_target(
    action,
    counting_status,
    outcome,
    completed_field,
    passed_field,
    failed_field,
):
    progress = _progress(
        _report(
            facts=(
                _fact(
                    f"NIFTY:{action}:{outcome}",
                    market="NIFTY",
                    action=action,
                    counting_status=counting_status,
                    officially_counted=False,
                    entry_occurred=False,
                    closed_position=False,
                    lifecycle_status="RESOLVED",
                    reconciliation_status="RECONCILED",
                    outcome=outcome,
                ),
            )
        )
    )

    nifty = progress.nifty

    assert nifty.completed_live_paper_trades == 0
    assert nifty.remaining_trade_count == 100
    assert getattr(nifty, completed_field) == 1

    expected_pass = int(
        outcome == "NO_TRADE_CORRECT"
    )
    expected_fail = int(
        outcome == "NO_TRADE_MISSED_MOVE"
    )

    assert getattr(nifty, passed_field) == expected_pass
    assert getattr(nifty, failed_field) == expected_fail


def test_wait_and_no_trade_are_independently_reconciled():
    progress = _progress(
        _report(
            facts=(
                _fact(
                    "nifty-wait-pass",
                    market="NIFTY",
                    action="WAIT",
                    counting_status="INCLUDED_WAIT",
                    outcome="NO_TRADE_CORRECT",
                ),
                _fact(
                    "nifty-wait-fail",
                    market="NIFTY",
                    action="WAIT",
                    counting_status="INCLUDED_WAIT",
                    outcome="NO_TRADE_MISSED_MOVE",
                ),
                _fact(
                    "nifty-no-trade-pass",
                    market="NIFTY",
                    action="NO_TRADE",
                    counting_status="INCLUDED_NON_TRADE",
                    outcome="NO_TRADE_CORRECT",
                ),
            )
        )
    )

    assert (
        progress.nifty.wait_completed,
        progress.nifty.wait_passed,
        progress.nifty.wait_failed,
    ) == (
        2,
        1,
        1,
    )

    assert (
        progress.nifty.no_trade_completed,
        progress.nifty.no_trade_passed,
        progress.nifty.no_trade_failed,
    ) == (
        1,
        1,
        0,
    )


def test_exclusion_analytics_remain_separate_from_trade_targets():
    progress = _progress(
        _report(
            excluded=(
                {"status": "EXCLUDED_REPLAY"},
                {"status": "EXCLUDED_INVALID_EVIDENCE"},
                {"status": "EXCLUDED_DATA_INCIDENT"},
            ),
            unresolved=(
                {"prediction_id": "pending-1"},
            ),
            incidents=(
                {
                    "resolved": False,
                    "severity": "WARNING",
                },
                {
                    "resolved": True,
                    "severity": "ERROR",
                },
                {
                    "resolved": True,
                    "severity": "INFO",
                },
            ),
            duplicates=(
                {"prediction_id": "duplicate-1"},
                {"prediction_id": "duplicate-2"},
            ),
        )
    )

    assert progress.replay_excluded == 1
    assert progress.duplicate_excluded == 2

    # Two excluded invalid/data records plus two fail-closed incidents.
    assert progress.invalid_excluded == 4
    assert progress.unresolved == 1

    assert progress.nifty.completed_live_paper_trades == 0
    assert progress.sensex.completed_live_paper_trades == 0


def test_certification_requires_100_completed_trades_for_each_market():
    facts = tuple(
        _fact(
            f"NIFTY:{index}",
            market="NIFTY",
            action="CALL",
            counting_status="INCLUDED",
            officially_counted=True,
            entry_occurred=True,
            closed_position=True,
            outcome="T1_HIT",
        )
        for index in range(100)
    ) + tuple(
        _fact(
            f"SENSEX:{index}",
            market="SENSEX",
            action="PUT",
            counting_status="INCLUDED",
            officially_counted=True,
            entry_occurred=True,
            closed_position=True,
            outcome="T1_HIT",
        )
        for index in range(99)
    )

    almost = _progress(
        _report(facts=facts)
    )

    assert almost.nifty.target_reached is True
    assert almost.sensex.target_reached is False
    assert almost.certification_complete is False

    complete = _progress(
        _report(
            facts=(
                facts
                + (
                    _fact(
                        "SENSEX:99",
                        market="SENSEX",
                        action="PUT",
                        counting_status="INCLUDED",
                        officially_counted=True,
                        entry_occurred=True,
                        closed_position=True,
                        outcome="T1_HIT",
                    ),
                )
            )
        )
    )

    assert complete.nifty.completed_live_paper_trades == 100
    assert complete.sensex.completed_live_paper_trades == 100
    assert complete.certification_complete is True


def test_contract_rejects_incoherent_wait_analytics():
    with pytest.raises(
        ValueError,
        match="WAIT reconciliation",
    ):
        Task9MarketProgressV1(
            market="NIFTY",
            target_trade_count=100,
            completed_live_paper_trades=0,
            pending_entered_trades=0,
            no_trade_completed=0,
            no_trade_passed=0,
            no_trade_failed=0,
            wait_completed=2,
            wait_passed=1,
            wait_failed=0,
        )


def test_serialization_is_paper_read_only_and_contains_wait_analytics():
    value = Task9LivePaperCertificationProgressV1(
        nifty=Task9MarketProgressV1(
            market="NIFTY",
            target_trade_count=100,
            completed_live_paper_trades=7,
            pending_entered_trades=1,
            no_trade_completed=3,
            no_trade_passed=2,
            no_trade_failed=1,
            wait_completed=4,
            wait_passed=3,
            wait_failed=1,
        ),
        sensex=Task9MarketProgressV1(
            market="SENSEX",
            target_trade_count=100,
            completed_live_paper_trades=5,
            pending_entered_trades=0,
            no_trade_completed=1,
            no_trade_passed=1,
            no_trade_failed=0,
            wait_completed=2,
            wait_passed=1,
            wait_failed=1,
        ),
        replay_excluded=2,
        duplicate_excluded=1,
        invalid_excluded=3,
        unresolved=4,
        certification_complete=False,
    )

    first = value.to_dict()
    second = value.to_dict()

    assert first == second

    assert first["execution_mode"] == "PAPER"
    assert first["live_execution_eligible"] is False
    assert first["broker_order_submission"] is False
    assert first["read_only"] is True

    assert first["nifty"]["wait_completed"] == 4
    assert first["nifty"]["wait_passed"] == 3
    assert first["nifty"]["wait_failed"] == 1
    assert first["nifty"]["remaining_trade_count"] == 93
    assert first["nifty"]["target_reached"] is False


def test_raw_progress_builder_fails_closed_on_unsafe_report():
    report = _report()
    unsafe = deepcopy(report)
    unsafe["execution_mode"] = "LIVE"

    with pytest.raises(
        ValueError,
        match="Task 9 daily report safety",
    ):
        _progress(unsafe)
