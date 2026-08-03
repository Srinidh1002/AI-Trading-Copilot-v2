"""Focused deterministic contract tests for the Task 8 certification seam.

The integration factory is deliberately injected: these tests use the
existing typed NIFTY/SENSEX coordinator fixtures, never a broker or network.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from services.certification.task8_live_paper_canary import (
    Task8CanaryDependenciesV1,
    run_task8_live_paper_canary,
)
from services.contracts.two_market_decision_policy_v1 import TwoMarketDecisionPolicyV1
from services.contracts.two_market_parent_cycle_input_v1 import TwoMarketParentCycleInputV1
from services.contracts.paper_orchestration_cycle_result_v1 import PaperOrchestrationCycleResultV1
from services.contracts.paper_orchestration_stage_result_v1 import PaperOrchestrationStageResultV1
from services.paper_orchestration.certified_live_provider_readers import CertifiedLiveProviderReaders
from services.paper_orchestration.certified_two_market_parent_runtime import run_certified_two_market_parent_runtime
from test_certified_two_market_parent_runtime import candidate_for, cycles
from test_two_market_runtime_readiness import OfflineAnalysisPipeline, OfflineOptionPipeline


NOW = datetime(2026, 8, 2, tzinfo=timezone.utc)


def _decision(scores=(80.0, 60.0), eligible=True):
    nifty, sensex = cycles()
    parent = TwoMarketParentCycleInputV1(
        parent_cycle_id="task8-parent", decision_result_id="task8-decision",
        nifty_child_result_id="task8-nifty", sensex_child_result_id="task8-sensex",
        nifty_observation_id=nifty.observation_id, sensex_observation_id=sensex.observation_id,
        requested_at=nifty.cycle_requested_at, completed_at=max(nifty.received_at, sensex.received_at),
        decision_policy=TwoMarketDecisionPolicyV1(180.0, 5.0),
    )
    calls = []
    def candidate(cycle, data, analysis, captured, shared_context, *, parent_cycle_id):
        calls.append(cycle.underlying_symbol)
        return candidate_for(cycle, data, score=scores[0] if cycle.underlying_symbol == "NIFTY" else scores[1], eligibility="ELIGIBLE" if eligible else "INELIGIBLE")
    readers = CertifiedLiveProviderReaders(quote_reader=lambda *_: None, analysis_pipeline=OfflineAnalysisPipeline(), option_decision_pipeline=OfflineOptionPipeline(), available_capital=10_000.0, candidate_reader=candidate)
    return lambda: run_certified_two_market_parent_runtime(parent, nifty_cycle=nifty, sensex_cycle=sensex, readers=readers), calls


def _dependencies(parent_cycle, planner):
    return Task8CanaryDependenciesV1(
        branch="p10-two-market-weekend-readiness", commit="b779062",
        preflight=lambda: {key: True for key in ("branch_worktree", "paper_mode", "live_execution_ineligible", "broker_submission_disabled", "nifty_provider", "sensex_provider", "routing", "persistence_writable", "journal_writable", "emergency_halt", "market_session_checked", "credentials_present")} | {"journal_status": "WRITABLE"},
        parent_cycle=parent_cycle, selected_planner=planner, monitoring=lambda: None,
        clock=lambda: NOW, id_factory=lambda: "task8-fixed", network_live_read_usage=False,
    )


def test_two_markets_are_evaluated_once_selected_only_and_loser_is_retained():
    parent_cycle, calls = _decision()
    planned = []
    def planner(market):
        planned.append(market)
        stage = PaperOrchestrationStageResultV1("stage", "cycle", "DATA", "COMPLETED", NOW, NOW)
        return PaperOrchestrationCycleResultV1("result", "cycle", "key", "0" * 64, "COMPLETED_NO_ACTION", "DATA", NOW, NOW, (stage,))
    result = run_task8_live_paper_canary(_dependencies(parent_cycle, planner))
    assert calls == ["NIFTY", "SENSEX"]
    assert planned == [("NIFTY", "NSE")]
    assert result.rejected_market == "SENSEX"
    assert "P6_PLAN_EVIDENCE_UNAVAILABLE" in result.pass_blockers


def test_no_trade_is_not_a_failure_when_every_gate_is_evidenced():
    parent_cycle, calls = _decision(eligible=False)
    result = run_task8_live_paper_canary(_dependencies(parent_cycle, lambda _: None))
    assert calls == ["NIFTY", "SENSEX"]
    assert result.passed is True
    assert result.selected_market == "NONE"
    assert result.final_action == "NO_TRADE"


def test_paper_safety_contract_rejects_broker_submission():
    parent_cycle, _ = _decision(eligible=False)
    try:
        Task8CanaryDependenciesV1(branch="b", commit="c", preflight=lambda: {}, parent_cycle=parent_cycle, selected_planner=lambda _: None, monitoring=lambda: None, clock=lambda: NOW, id_factory=lambda: "id", broker_order_submission=True)
    except ValueError as exc:
        assert "PAPER-only" in str(exc)
    else:
        raise AssertionError("broker submission must be rejected")
