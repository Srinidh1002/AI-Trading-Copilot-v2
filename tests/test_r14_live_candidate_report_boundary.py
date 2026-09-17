from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.certification.task1c_parent_only_live_canary import (
    Task1CParentOnlyReportV1,
)


NOW = datetime(
    2026,
    8,
    4,
    8,
    0,
    tzinfo=timezone.utc,
)


def report() -> Task1CParentOnlyReportV1:
    return Task1CParentOnlyReportV1(
        run_id="r1-4-offline",
        cycle_id="parent-cycle",
        started_at=NOW,
        completed_at=NOW,
        execution_mode="PAPER",
        live_execution_eligible=False,
        broker_order_submission=False,
        parent_action="NO_TRADE",
        selected_market="NONE",
        parent_status="COMPLETED",
        parent_blockers=("NO_ELIGIBLE_MARKET",),
        parent_warnings=(),
        nifty={
            "terminal_status": "COMPLETED",
            "candidate_available": True,
            "action": "UNAVAILABLE",
        },
        sensex={
            "terminal_status": "COMPLETED",
            "candidate_available": True,
            "action": "UNAVAILABLE",
        },
        india_vix={
            "capture_status": "READY",
            "same_observation_reused": True,
        },
        external_context={
            "same_shared_input_reused_by_both_markets": True,
        },
        call_counts={
            "planner_invocations": 0,
            "lifecycle_invocations": 0,
            "monitoring_mutations": 0,
            "broker_order_invocations": 0,
        },
    )


def test_report_proves_both_candidates_and_paper_safety():
    value = report()

    assert value.execution_mode == "PAPER"
    assert value.live_execution_eligible is False
    assert value.broker_order_submission is False
    assert value.parent_status == "COMPLETED"

    assert value.nifty["terminal_status"] == "COMPLETED"
    assert value.nifty["candidate_available"] is True

    assert value.sensex["terminal_status"] == "COMPLETED"
    assert value.sensex["candidate_available"] is True

    assert value.call_counts == {
        "planner_invocations": 0,
        "lifecycle_invocations": 0,
        "monitoring_mutations": 0,
        "broker_order_invocations": 0,
    }


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    (
        ("execution_mode", "LIVE"),
        ("live_execution_eligible", True),
        ("broker_order_submission", True),
    ),
)
def test_report_rejects_non_paper_safety(
    field_name,
    field_value,
):
    with pytest.raises(ValueError, match="parent-only safety"):
        replace(
            report(),
            **{field_name: field_value},
        )


@pytest.mark.parametrize(
    "counter",
    (
        "planner_invocations",
        "lifecycle_invocations",
        "monitoring_mutations",
        "broker_order_invocations",
    ),
)
def test_report_rejects_downstream_or_broker_activity(counter):
    counts = dict(report().call_counts)
    counts[counter] = 1

    with pytest.raises(
        ValueError,
        match=f"{counter} must remain zero",
    ):
        replace(
            report(),
            call_counts=counts,
        )
