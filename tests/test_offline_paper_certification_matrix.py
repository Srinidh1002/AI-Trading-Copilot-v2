"""Task 7 Slice 1 deterministic certification matrix tests."""
from datetime import datetime, timezone

import pytest

from services.certification.offline_paper_certification_matrix import (
    build_offline_paper_certification_report,
)
from services.contracts.offline_paper_certification_v1 import (
    OfflinePaperCertificationCheckV1,
    OfflinePaperCertificationReportV1,
)


NOW = datetime(2026, 8, 3, 11, 0, tzinfo=timezone.utc)


def build(**changes):
    values = dict(
        report_id="report-1",
        generated_at=NOW,
        branch_name="p10-two-market-weekend-readiness",
        commit_sha="077a851",
    )
    values.update(changes)
    return build_offline_paper_certification_report(**values)


def test_complete_matrix_passes_offline():
    result = build()

    assert result.overall_status == "PASSED"
    assert result.passed_count == 6
    assert result.failed_count == 0
    assert result.blocked_count == 0
    assert result.execution_mode == "PAPER"
    assert result.network_access_used is False
    assert result.broker_submission_enabled is False
    assert result.live_execution_eligible is False


def test_matrix_contains_all_required_categories():
    result = build()

    assert {check.category for check in result.checks} == {
        "TWO_MARKET",
        "CAPITAL_RISK",
        "PAPER_LIFECYCLE",
        "RESTART_RECOVERY",
        "OPERATOR_DASHBOARD",
        "SAFETY_ISOLATION",
    }


def test_failed_check_makes_report_failed():
    result = build(
        failed_check_ids=("paper-lifecycle",),
    )

    assert result.overall_status == "FAILED"
    assert result.failed_count == 1
    failed = next(
        check
        for check in result.checks
        if check.check_id == "paper-lifecycle"
    )
    assert failed.status == "FAILED"
    assert failed.blockers == (
        "CERTIFICATION_ASSERTION_FAILED",
    )


def test_blocked_check_makes_report_blocked():
    result = build(
        blocked_check_ids=("operator-dashboard",),
    )

    assert result.overall_status == "BLOCKED"
    assert result.blocked_count == 1


def test_failure_takes_precedence_over_blocked():
    result = build(
        failed_check_ids=("two-market-selection",),
        blocked_check_ids=("operator-dashboard",),
    )

    assert result.overall_status == "FAILED"
    assert result.failed_count == 1
    assert result.blocked_count == 1


def test_unknown_check_id_fails_closed():
    with pytest.raises(ValueError, match="unknown"):
        build(failed_check_ids=("not-real",))


def test_same_check_cannot_be_failed_and_blocked():
    with pytest.raises(ValueError, match="both"):
        build(
            failed_check_ids=("paper-lifecycle",),
            blocked_check_ids=("paper-lifecycle",),
        )


def test_passed_check_cannot_contain_blockers():
    with pytest.raises(ValueError, match="passed"):
        OfflinePaperCertificationCheckV1(
            check_id="check-1",
            category="TWO_MARKET",
            name="Check",
            status="PASSED",
            evidence=("Evidence",),
            blockers=("BLOCKED",),
        )


def test_report_count_mismatch_fails_closed():
    check = OfflinePaperCertificationCheckV1(
        check_id="check-1",
        category="TWO_MARKET",
        name="Check",
        status="PASSED",
        evidence=("Evidence",),
    )

    with pytest.raises(ValueError, match="passed_count mismatch"):
        OfflinePaperCertificationReportV1(
            report_id="report-1",
            generated_at=NOW,
            branch_name="branch",
            commit_sha="abc123",
            checks=(check,),
            overall_status="PASSED",
            passed_count=0,
            failed_count=0,
            blocked_count=0,
        )
