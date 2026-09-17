from dataclasses import replace

import pytest

from services.certification.task9_live_paper_certification_progress_builder import (
    build_task9_live_paper_certification_progress,
)
from services.contracts.task9_live_paper_certification_progress_v1 import (
    Task9LivePaperCertificationProgressV1,
    Task9MarketProgressV1,
)
from tests.r79_reporting_helpers import (
    build_daily,
)


def test_market_progress_requires_exact_100_target():
    with pytest.raises(
        ValueError,
        match="exactly 100 trades per market",
    ):
        Task9MarketProgressV1(
            market="NIFTY",
            target_trade_count=40,
            completed_live_paper_trades=0,
            pending_entered_trades=0,
            no_trade_completed=0,
            no_trade_passed=0,
            no_trade_failed=0,
        )


def test_no_trade_pass_fail_must_reconcile():
    with pytest.raises(
        ValueError,
        match="NO_TRADE reconciliation",
    ):
        Task9MarketProgressV1(
            market="NIFTY",
            target_trade_count=100,
            completed_live_paper_trades=0,
            pending_entered_trades=0,
            no_trade_completed=2,
            no_trade_passed=1,
            no_trade_failed=0,
        )


def test_certification_requires_100_completed_trades_in_both_markets():
    nifty = Task9MarketProgressV1(
        market="NIFTY",
        target_trade_count=100,
        completed_live_paper_trades=100,
        pending_entered_trades=3,
        no_trade_completed=25,
        no_trade_passed=20,
        no_trade_failed=5,
    )
    sensex = Task9MarketProgressV1(
        market="SENSEX",
        target_trade_count=100,
        completed_live_paper_trades=99,
        pending_entered_trades=1,
        no_trade_completed=30,
        no_trade_passed=24,
        no_trade_failed=6,
    )

    assert nifty.target_reached is True
    assert nifty.remaining_trade_count == 0
    assert sensex.target_reached is False
    assert sensex.remaining_trade_count == 1

    progress = Task9LivePaperCertificationProgressV1(
        nifty=nifty,
        sensex=sensex,
        replay_excluded=0,
        duplicate_excluded=0,
        invalid_excluded=0,
        unresolved=0,
        certification_complete=False,
    )

    assert progress.certification_complete is False

    completed_sensex = replace(
        sensex,
        completed_live_paper_trades=100,
    )

    completed = Task9LivePaperCertificationProgressV1(
        nifty=nifty,
        sensex=completed_sensex,
        replay_excluded=0,
        duplicate_excluded=0,
        invalid_excluded=0,
        unresolved=0,
        certification_complete=True,
    )

    assert completed.certification_complete is True


def test_completion_flag_cannot_claim_success_early():
    nifty = Task9MarketProgressV1(
        market="NIFTY",
        target_trade_count=100,
        completed_live_paper_trades=100,
        pending_entered_trades=0,
        no_trade_completed=0,
        no_trade_passed=0,
        no_trade_failed=0,
    )
    sensex = Task9MarketProgressV1(
        market="SENSEX",
        target_trade_count=100,
        completed_live_paper_trades=99,
        pending_entered_trades=0,
        no_trade_completed=0,
        no_trade_passed=0,
        no_trade_failed=0,
    )

    with pytest.raises(
        ValueError,
        match="certification completion coherence",
    ):
        Task9LivePaperCertificationProgressV1(
            nifty=nifty,
            sensex=sensex,
            replay_excluded=0,
            duplicate_excluded=0,
            invalid_excluded=0,
            unresolved=0,
            certification_complete=True,
        )


def test_daily_report_counts_closed_trade_and_no_trade_separately():
    report = build_daily()

    progress = build_task9_live_paper_certification_progress(
        (report,)
    )

    assert progress.nifty.completed_live_paper_trades == 1
    assert progress.nifty.no_trade_completed == 1
    assert (
        progress.nifty.no_trade_passed
        + progress.nifty.no_trade_failed
        == 1
    )

    assert progress.nifty.remaining_trade_count == 99
    assert progress.nifty.target_reached is False

    assert progress.sensex.completed_live_paper_trades == 0
    assert progress.sensex.no_trade_completed == 0
    assert progress.sensex.remaining_trade_count == 100

    assert progress.certification_complete is False

    # The reporting helper contains one blocked duplicate attempt.
    assert progress.duplicate_excluded == 1


def test_replay_prediction_is_excluded_not_added_to_trade_target():
    report = build_daily(include_excluded=True)

    progress = build_task9_live_paper_certification_progress(
        (report,)
    )

    assert progress.replay_excluded == 1
    assert progress.nifty.completed_live_paper_trades == 1
    assert progress.sensex.completed_live_paper_trades == 0


def test_same_daily_session_cannot_be_aggregated_twice():
    report = build_daily()

    with pytest.raises(
        ValueError,
        match="duplicate Task 9 daily certification session",
    ):
        build_task9_live_paper_certification_progress(
            (report, report)
        )


def test_same_prediction_cannot_increment_progress_twice():
    first = build_daily(
        report_id="daily-first",
    )
    second = replace(
        first,
        report_id="daily-second",
        session_date=(
            first.session_date.replace(
                day=first.session_date.day + 1
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="duplicate prediction across Task 9 reports",
    ):
        build_task9_live_paper_certification_progress(
            (first, second)
        )


def test_progress_remains_paper_only():
    market = Task9MarketProgressV1(
        market="NIFTY",
        target_trade_count=100,
        completed_live_paper_trades=0,
        pending_entered_trades=0,
        no_trade_completed=0,
        no_trade_passed=0,
        no_trade_failed=0,
    )
    sensex = replace(
        market,
        market="SENSEX",
    )

    with pytest.raises(
        ValueError,
        match="PAPER-only",
    ):
        Task9LivePaperCertificationProgressV1(
            nifty=market,
            sensex=sensex,
            replay_excluded=0,
            duplicate_excluded=0,
            invalid_excluded=0,
            unresolved=0,
            certification_complete=False,
            broker_order_submission=True,
        )


def test_blocked_duplicate_attempt_never_increments_trade_target():
    report = build_daily()

    original = (
        build_task9_live_paper_certification_progress(
            (report,)
        )
    )

    additional_duplicate = replace(
        report.duplicate_attempts[0],
        attempt_id="duplicate-2",
        duplicate_type="ENTRY",
        reference_id="already-counted-entry",
        reason_codes=("IDEMPOTENCY_HIT",),
    )

    duplicate_heavy_report = replace(
        report,
        duplicate_attempts=(
            report.duplicate_attempts
            + (additional_duplicate,)
        ),
        duplicate_distribution=(
            ("ENTRY", 1),
            ("PREDICTION", 1),
        ),
    )

    progress = (
        build_task9_live_paper_certification_progress(
            (duplicate_heavy_report,)
        )
    )

    assert (
        progress.nifty.completed_live_paper_trades
        == original.nifty.completed_live_paper_trades
        == 1
    )
    assert (
        progress.sensex.completed_live_paper_trades
        == original.sensex.completed_live_paper_trades
        == 0
    )
    assert progress.duplicate_excluded == 2


def test_resolved_warning_incident_is_visible_but_not_invalid_exclusion():
    report = build_daily()

    assert len(report.incidents) == 1
    assert report.incidents[0].severity == "WARNING"
    assert report.incidents[0].resolved is True

    progress = (
        build_task9_live_paper_certification_progress(
            (report,)
        )
    )

    assert progress.invalid_excluded == 0
    assert progress.nifty.completed_live_paper_trades == 1


def test_unresolved_warning_incident_is_invalid_exclusion_only():
    report = build_daily()

    incident = replace(
        report.incidents[0],
        resolved=False,
    )

    adverse = replace(
        report,
        incidents=(incident,),
    )

    progress = (
        build_task9_live_paper_certification_progress(
            (adverse,)
        )
    )

    assert progress.invalid_excluded == 1
    assert progress.nifty.completed_live_paper_trades == 1


@pytest.mark.parametrize(
    "severity",
    (
        "ERROR",
        "CRITICAL",
    ),
)
def test_resolved_severe_incident_remains_invalid_exclusion(
    severity,
):
    report = build_daily()

    incident = replace(
        report.incidents[0],
        severity=severity,
        resolved=True,
    )

    adverse = replace(
        report,
        incidents=(incident,),
    )

    progress = (
        build_task9_live_paper_certification_progress(
            (adverse,)
        )
    )

    assert progress.invalid_excluded == 1
    assert progress.nifty.completed_live_paper_trades == 1
