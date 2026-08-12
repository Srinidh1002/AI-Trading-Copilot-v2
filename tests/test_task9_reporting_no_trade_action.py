from dataclasses import replace
import pytest

from services.reports.paper_certification_daily_report import (
    build_paper_certification_daily_report,
)
from services.contracts.paper_certification_reporting_v1 import (
    CertificationPredictionFactV1,
)
from services.certification.task9_live_paper_certification_progress_builder import (
    build_task9_live_paper_certification_progress_from_raw,
)
from tests.r79_reporting_helpers import (
    NOW,
    counting_decision,
    reconciliation,
    wait_outcome,
    wait_prediction,
)


@pytest.mark.parametrize(
    ("outcome_name", "passed", "failed"),
    (("NO_TRADE_CORRECT", 1, 0), ("NO_TRADE_MISSED_MOVE", 0, 1)),
)
def test_no_trade_is_a_distinct_uncounted_daily_reporting_action(
    outcome_name,
    passed,
    failed,
):
    wait = wait_prediction()
    no_trade = replace(
        wait,
        prediction_id="prediction:parent-no-trade:NIFTY:NSE",
        parent_cycle_id="parent-no-trade",
        decision_result_id="decision-no-trade",
        child_result_id="child-no-trade",
        observation_id="observation-no-trade",
        predicted_action="NO_TRADE",
    )
    wait_outcome_value = wait_outcome(wait)
    no_trade_outcome = replace(
        wait_outcome(no_trade),
        outcome_id="lifecycle-outcome-no-trade",
        outcome=outcome_name,
    )
    non_trade = replace(
        counting_decision(no_trade, "n"),
        status="INCLUDED_NON_TRADE",
        countable=False,
        pending=False,
        outcome_id=no_trade_outcome.outcome_id,
        reason_codes=(),
    )
    completed_wait = replace(
        counting_decision(wait, "w"),
        status="INCLUDED_WAIT",
        countable=False,
        pending=False,
        outcome_id=wait_outcome_value.outcome_id,
        reason_codes=(),
    )
    report = build_paper_certification_daily_report(
        report_id="no-trade-action-report",
        session_date=NOW.date(),
        generated_at=NOW,
        starting_capital=100_000.0,
        predictions=(wait, no_trade),
        counting_decisions=(completed_wait, non_trade),
        lifecycle_outcomes=(wait_outcome_value, no_trade_outcome),
        reconciliations=(reconciliation(no_trade, no_trade_outcome),),
        positions=(),
    )
    facts = {item.action: item for item in report.prediction_facts}
    assert set(facts) == {"WAIT", "NO_TRADE"}
    assert type(facts["NO_TRADE"]) is CertificationPredictionFactV1
    assert facts["NO_TRADE"].officially_counted is False
    assert facts["NO_TRADE"].counting_status == "INCLUDED_NON_TRADE"
    assert facts["WAIT"].officially_counted is False
    assert facts["WAIT"].counting_status == "INCLUDED_WAIT"
    assert report.completed_non_trade_count == 2
    assert report.official_prediction_count == 0
    assert report.pending_outcome_count == 0
    assert report.excluded_prediction_count == 0
    assert report.unresolved_audit == ()
    assert (
        report.official_prediction_count
        + report.completed_non_trade_count
        + report.pending_outcome_count
        + report.excluded_prediction_count
        == report.source_prediction_count
    )
    assert dict(report.action_distribution) == {
        "CALL": 0,
        "PUT": 0,
        "WAIT": 1,
        "NO_TRADE": 1,
    }
    progress = build_task9_live_paper_certification_progress_from_raw((report.to_dict(),))
    assert progress.nifty.completed_live_paper_trades == 0
    assert (progress.nifty.no_trade_completed, progress.nifty.no_trade_passed, progress.nifty.no_trade_failed) == (1, passed, failed)


def test_included_trade_contract_still_rejects_non_countable_payload():
    no_trade = replace(wait_prediction(), predicted_action="NO_TRADE")
    with pytest.raises(ValueError, match="INCLUDED decision coherence"):
        replace(
            counting_decision(no_trade, "x"),
            countable=False,
        )
