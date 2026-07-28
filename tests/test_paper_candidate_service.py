from datetime import datetime

from services.contracts.final_decision_v1 import FinalDecisionV1
from services.paper.paper_candidate_service import prepare_paper_candidate


def test_analysis_only_decision_needs_a_trade_plan_and_does_not_prepare_candidate():
    now = datetime.fromisoformat("2026-07-10T10:00:00+05:30")
    decision = FinalDecisionV1(
        snapshot_id="snapshot-1", decision_id="decision-1", symbol="NIFTY",
        exchange="NSE", instrument_type="INDEX", created_at=now,
        market_timestamp=now, action="BUY", authorization_status="ANALYSIS_ONLY",
        execution_status="NOT_REQUESTED",
    )

    result = prepare_paper_candidate(decision)

    assert result.status == "NEEDS_TRADE_PLAN"
    assert result.candidate is None
