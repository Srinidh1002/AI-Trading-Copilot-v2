from dataclasses import replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.contracts.final_decision_v1 import (
    DataHealthSummary,
    FinalDecisionV1,
    RiskSummary,
    TradePlanV1,
)
from services.paper.paper_candidate_service import (
    execute_paper_candidate,
    prepare_paper_candidate,
)


NOW = datetime(2026, 7, 25, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def _decision(*, authorization="PAPER_READY", confidence=None, risk_level="UNKNOWN"):
    return FinalDecisionV1(
        snapshot_id="snapshot-1",
        decision_id="decision-1",
        symbol="NIFTY",
        exchange="NSE",
        instrument_type="OPTION",
        created_at=NOW,
        market_timestamp=NOW,
        action="BUY",
        authorization_status=authorization,
        execution_status="NOT_REQUESTED",
        option_type="CE",
        confidence=confidence,
        trade_plan=TradePlanV1(
            entry_price=100.0,
            stop_loss=90.0,
            targets=(110.0, 120.0),
            quantity=65,
            lots=1,
            risk_reward_ratio=2.0,
            maximum_planned_loss=650.0,
        ),
        risk=RiskSummary(risk_status="APPROVED", risk_level=risk_level),
        data_health=DataHealthSummary(overall_status="VALID", validation_passed=True),
    )


def _candidate(decision=None):
    decision = decision or _decision()
    preparation = prepare_paper_candidate(
        decision,
        instrument_identity={
            "option_type": "CE",
            "tradingsymbol": "NIFTY26JUL25000CE",
            "instrument_token": "12345",
            "lot_size": 65,
        },
        expires_at=NOW + timedelta(minutes=5),
    )
    assert preparation.candidate is not None
    return preparation.candidate


def test_explicit_approval_is_required():
    decision = _decision()
    calls = []
    result = execute_paper_candidate(
        _candidate(decision), decision, approved=False, now=NOW,
        executor=lambda payload: calls.append(payload),
    )
    assert result.submitted is False
    assert calls == []


def test_expired_candidate_is_rejected_without_executor_call():
    decision = _decision()
    candidate = _candidate(decision)
    calls = []

    result = execute_paper_candidate(
        candidate,
        decision,
        approved=True,
        now=candidate.expires_at,
        executor=lambda payload: calls.append(payload),
    )

    assert result.submitted is False
    assert result.reason == "Paper candidate is stale or expired."
    assert calls == []


def test_identity_mismatch_is_rejected():
    decision = _decision()
    candidate = replace(_candidate(decision), decision_id="different")
    calls = []
    result = execute_paper_candidate(
        candidate, decision, approved=True, now=NOW,
        executor=lambda payload: calls.append(payload),
    )
    assert result.submitted is False
    assert calls == []


def test_executor_called_once_for_valid_candidate():
    decision = _decision(confidence=72.5, risk_level="MEDIUM")
    candidate = _candidate(decision)
    calls = []

    def executor(payload):
        calls.append(payload)
        return {"executed": True, "status": "SUBMITTED", "reason": "ok"}

    result = execute_paper_candidate(
        candidate, decision, approved=True, now=NOW, executor=executor,
    )
    assert result.submitted is True
    assert len(calls) == 1
    assert calls[0]["confidence"] == 72.5
    assert calls[0]["risk_level"] == "MEDIUM"


def test_missing_confidence_and_unknown_risk_are_not_fabricated():
    decision = _decision(confidence=None, risk_level="UNKNOWN")
    candidate = _candidate(decision)
    calls = []

    execute_paper_candidate(
        candidate,
        decision,
        approved=True,
        now=NOW,
        executor=lambda payload: calls.append(payload)
        or {"executed": True, "status": "SUBMITTED", "reason": "ok"},
    )

    assert len(calls) == 1
    assert "confidence" not in calls[0]
    assert "risk_level" not in calls[0]


def test_executor_exception_is_safe_failure():
    decision = _decision()
    result = execute_paper_candidate(
        _candidate(decision),
        decision,
        approved=True,
        now=NOW,
        executor=lambda payload: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert result.submitted is False
    assert result.reason == "Paper executor failed."
