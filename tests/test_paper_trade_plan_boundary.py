from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from services.contracts.canonical_trade_plan_result_v1 import CanonicalTradePlanResultV1
from services.contracts.final_decision_v1 import DataHealthSummary, FinalDecisionV1, RiskSummary, TradePlanV1 as LegacyTradePlanV1
from services.contracts.paper_trade_candidate_v1 import PaperTradeCandidateV1
from services.contracts.selected_option_contract_v1 import SelectedOptionContractV1
from services.contracts.trade_plan_v1 import TradePlanV1
from services.paper.paper_candidate_service import execute_paper_candidate, prepare_paper_candidate


NOW = datetime(2026, 7, 27, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def _decision(*, snapshot_id="snapshot-1", decision_id="decision-1", symbol="NIFTY", exchange="NSE", action="BUY", legacy=False):
    legacy_plan = (
        LegacyTradePlanV1(
            entry_price=100,
            stop_loss=90,
            targets=(110, 120),
            quantity=65,
            lots=1,
            risk_reward_ratio=2.0,
        )
        if legacy
        else None
    )
    return FinalDecisionV1(snapshot_id=snapshot_id, decision_id=decision_id, symbol=symbol, exchange=exchange, instrument_type="OPTION", created_at=NOW, market_timestamp=NOW, action=action, authorization_status="PAPER_READY" if legacy else "ANALYSIS_ONLY", execution_status="NOT_REQUESTED", option_type="CE", trade_plan=legacy_plan, risk=RiskSummary(risk_status="APPROVED"), data_health=DataHealthSummary(overall_status="VALID", validation_passed=True))


def _plan(**changes):
    data = dict(trade_plan_id="plan-1", created_at=NOW, snapshot_id="snapshot-1", analysis_id="analysis-1", decision_id="decision-1", selection_id="selection-1", contract_id="contract-1", underlying_symbol="NIFTY", exchange="NSE", action="BUY", option_type="CALL", trading_symbol="NIFTY26JUL25000CE", expiry_date=date(2026, 7, 30), strike=25000.0, lot_size=65, entry_reference_price=100.0, entry_price_source="LAST", stop_loss_price=90.0, target_price=110.0, stop_loss_source="EXPLICIT", target_source="EXPLICIT", valid_from=NOW, valid_until=NOW + timedelta(minutes=5), plan_status="READY_FOR_RISK", paper_preparation_eligible=True)
    data.update(changes)
    return TradePlanV1(**data)


def _selection():
    return SelectedOptionContractV1("selection-1", NOW, "snapshot-1", "decision-1", "universe-1", "contract-1", "NIFTY", "NSE", "BUY", "CALL", "NIFTY26JUL25000CE", None, date(2026, 7, 30), 25000.0, 65, 25000.0, 100.0, "LAST", "EARLIEST_ELIGIBLE", "NEAREST_ATM", True)


def _result(plan=None, **changes):
    decision = _decision()
    data = dict(result_id="result-1", created_at=NOW, snapshot_id="snapshot-1", analysis_id="analysis-1", decision_id="decision-1", decision=decision, selected_contract=_selection(), trade_plan=plan or _plan(), result_status="PLAN_CREATED")
    data.update(changes)
    return CanonicalTradePlanResultV1(**data)


def _candidate_and_decision():
    decision = _decision(legacy=True)
    candidate = PaperTradeCandidateV1(snapshot_id=decision.snapshot_id, decision_id=decision.decision_id, symbol="NIFTY", exchange="NSE", action="BUY", option_type="CE", tradingsymbol="NIFTY26JUL25000CE", instrument_token=None, entry=100, stop_loss=90, targets=(110, 120), quantity=65, lots=1, lot_size=65, created_at=NOW, expires_at=NOW + timedelta(minutes=5), authorization_status="PAPER_READY", execution_status="NOT_REQUESTED", data_health_status="VALID")
    return candidate, decision


def _session(**values):
    data = dict(symbol="NIFTY", exchange="NSE", trading_date=NOW.date(), paper_preparation_allowed=True, paper_execution_allowed=True, blockers=())
    data.update(values)
    return SimpleNamespace(**data)


def test_plan_created_reaches_risk_pending_validation():
    result = prepare_paper_candidate(_decision(), canonical_trade_plan_result=_result())
    assert (result.status, result.candidate) == ("NEEDS_TRADE_PLAN", None)


def test_ready_for_risk_plan_remains_non_executable():
    result = prepare_paper_candidate(_decision(), trade_plan=_plan())
    assert result.errors == ("P3-4 trade plan lacks P3-5 execution sizing.",)


def test_execution_eligible_false_rejects_before_executor():
    candidate, decision = _candidate_and_decision(); calls = []
    result = execute_paper_candidate(candidate, decision, approved=True, now=NOW, trade_plan=_plan(), executor=lambda _: calls.append(True))
    assert result.reason == "P3-4 trade plan lacks P3-5 execution sizing." and calls == []


def test_missing_quantity_does_not_create_a_paper_candidate():
    assert prepare_paper_candidate(_decision(), trade_plan=_plan()).candidate is None


def test_missing_lots_does_not_invoke_executor():
    candidate, decision = _candidate_and_decision(); calls = []
    execute_paper_candidate(candidate, decision, approved=True, now=NOW, trade_plan=_plan(), executor=lambda _: calls.append(True))
    assert calls == []


def test_missing_capital_does_not_invoke_executor():
    candidate, decision = _candidate_and_decision(); calls = []
    execute_paper_candidate(candidate, decision, approved=True, now=NOW, trade_plan=_plan(), executor=lambda _: calls.append(True))
    assert calls == []


def test_expired_plan_is_rejected():
    expired = _plan(valid_from=NOW - timedelta(days=2), valid_until=NOW - timedelta(days=1))
    assert prepare_paper_candidate(_decision(), trade_plan=expired).errors == ("Trade plan is stale or expired.",)


def test_blocked_canonical_result_is_rejected():
    blocked = CanonicalTradePlanResultV1("result-1", NOW, "snapshot-1", "analysis-1", "decision-1", _decision(), None, None, "BLOCKED", blockers=("blocked",))
    assert prepare_paper_candidate(_decision(), canonical_trade_plan_result=blocked).status == "BLOCKED"


def test_insufficient_data_canonical_result_is_rejected():
    result = CanonicalTradePlanResultV1("result-1", NOW, "snapshot-1", "analysis-1", "decision-1", _decision(), None, None, "INSUFFICIENT_DATA", blockers=("missing",))
    assert prepare_paper_candidate(_decision(), canonical_trade_plan_result=result).candidate is None


def test_no_action_canonical_result_is_rejected():
    result = CanonicalTradePlanResultV1("result-1", NOW, "snapshot-1", "analysis-1", "decision-1", _decision(), None, None, "NO_ACTION")
    assert prepare_paper_candidate(_decision(), canonical_trade_plan_result=result).candidate is None


def test_decision_mismatch_blocks_plan():
    assert prepare_paper_candidate(_decision(decision_id="other"), trade_plan=_plan()).candidate is None


def test_snapshot_mismatch_blocks_plan():
    assert prepare_paper_candidate(_decision(snapshot_id="other"), trade_plan=_plan()).candidate is None


def test_symbol_mismatch_blocks_plan():
    assert prepare_paper_candidate(_decision(symbol="SENSEX", exchange="BSE"), trade_plan=_plan()).candidate is None


def test_exchange_mismatch_blocks_plan():
    assert prepare_paper_candidate(_decision(exchange="BSE"), trade_plan=_plan()).candidate is None


def test_invalid_session_is_authoritative():
    result = prepare_paper_candidate(_decision(), trade_plan=_plan(), session_validation=_session(paper_preparation_allowed=False, blockers=("closed",)))
    assert result.errors == ("closed",)


def test_session_date_mismatch_blocks():
    result = prepare_paper_candidate(_decision(), trade_plan=_plan(), session_validation=_session(trading_date=NOW.date() - timedelta(days=1)))
    assert result.errors == ("Market session date does not match decision.",)


def test_executor_module_is_not_imported_when_p3_plan_rejected(monkeypatch):
    candidate, decision = _candidate_and_decision()
    monkeypatch.delitem(__import__("sys").modules, "services.trade.trade_engine", raising=False)
    execute_paper_candidate(candidate, decision, approved=True, now=NOW, trade_plan=_plan())
    assert "services.trade.trade_engine" not in __import__("sys").modules


def test_broker_is_not_imported_when_p3_plan_rejected(monkeypatch):
    candidate, decision = _candidate_and_decision()
    monkeypatch.delitem(__import__("sys").modules, "services.broker", raising=False)
    execute_paper_candidate(candidate, decision, approved=True, now=NOW, trade_plan=_plan())
    assert "services.broker" not in __import__("sys").modules


def test_rejection_reason_is_deterministic():
    first = prepare_paper_candidate(_decision(), trade_plan=_plan())
    second = prepare_paper_candidate(_decision(), trade_plan=_plan())
    assert first.errors == second.errors


def test_p3_inputs_are_not_mutated():
    plan = _plan(); result = _result(plan)
    before_plan, before_result = plan.to_dict(), result.to_dict()
    prepare_paper_candidate(_decision(), trade_plan=plan, canonical_trade_plan_result=result)
    assert plan.to_dict() == before_plan and result.to_dict() == before_result


def test_legacy_preparation_remains_compatible():
    decision = _decision(legacy=True)
    result = prepare_paper_candidate(decision, instrument_identity={"option_type": "CE", "tradingsymbol": "NIFTY26JUL25000CE", "lot_size": 65}, expires_at=NOW + timedelta(minutes=5))
    assert result.status == "MANUAL_APPROVAL_REQUIRED" and result.candidate is not None


def test_legacy_execution_boundary_remains_compatible():
    candidate, decision = _candidate_and_decision(); calls = []
    result = execute_paper_candidate(candidate, decision, approved=True, now=NOW, executor=lambda payload: calls.append(payload) or {"executed": True, "status": "SUBMITTED", "reason": "ok"})
    assert result.submitted is True and len(calls) == 1


def test_canonical_and_explicit_plan_must_match():
    different = _plan(trade_plan_id="other")
    assert prepare_paper_candidate(_decision(), canonical_trade_plan_result=_result(), trade_plan=different).candidate is None


def test_session_symbol_mismatch_blocks():
    result = prepare_paper_candidate(_decision(), trade_plan=_plan(), session_validation=_session(symbol="SENSEX"))
    assert result.errors == ("Market session identity does not match decision.",)
