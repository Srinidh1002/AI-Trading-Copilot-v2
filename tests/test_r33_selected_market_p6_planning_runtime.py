"""R3.3 fail-closed selected-market planning certification."""
from dataclasses import replace
from pathlib import Path

from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    SelectedMarketP6PlanningResultV1,
    adapt_selected_market_p6_to_cycle_result,
    execute_selected_market_p6_planning,
)
from test_selected_market_planning_bridge import selected_decision


def _no_trade_decision() -> TwoMarketDecisionResultV1:
    decision = selected_decision()
    entries = tuple(
        replace(
            entry,
            eligible_for_comparison=False,
            rank_value=0.0,
            outcome_reason="INELIGIBLE",
            child=replace(
                entry.child,
                terminal_status="FAILED",
                candidate=None,
                errors=("POLICY_BLOCKED",),
            ),
        )
        for entry in decision.entries
    )
    return TwoMarketDecisionResultV1(
        decision_result_id="r33-no-trade",
        parent_cycle_id=decision.parent_cycle_id,
        requested_at=decision.requested_at,
        completed_at=decision.completed_at,
        entries=entries,
        decision="NO_TRADE",
        selected_market=None,
        selected_candidate_id=None,
        timestamp_skew_seconds=0.0,
        blockers=("NO_ELIGIBLE_MARKET",),
    )


def test_missing_exact_p6_evidence_fails_closed_before_any_p6_stage():
    decision = selected_decision()
    result = execute_selected_market_p6_planning(
        bridge_result_id="r33-missing-evidence",
        decision=decision,
        selected_cycle=None,
        certified_p6_input_bundle=None,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )

    assert type(result) is SelectedMarketP6PlanningResultV1
    assert result.status == "BLOCKED"
    assert result.planning_result is None
    assert result.blockers == ("SELECTED_P6_CYCLE_EVIDENCE_MISSING",)


def test_no_trade_has_no_selected_planning_or_geometry():
    decision = _no_trade_decision()
    result = execute_selected_market_p6_planning(
        bridge_result_id="r33-no-trade",
        decision=decision,
        selected_cycle=None,
        certified_p6_input_bundle=None,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )

    assert result.status == "NO_TRADE"
    assert result.planning_result is None
    assert result.bridge.selected_market is None


def test_default_production_composition_no_longer_uses_lifecycle_placeholder():
    from services.certification.task8_live_paper_default_composition import (
        build_task8_dependencies,
    )

    dependencies = build_task8_dependencies()
    source = Path(
        "services/certification/task8_live_paper_default_composition.py"
    ).read_text(encoding="utf-8")

    assert dependencies.selected_planner.__name__ == "selected_planner"
    assert "selected-market lifecycle wiring is unavailable" not in source
    assert "execute_selected_market_p6_planning(" in source
    assert "certified_p6_input_bundle=None" in source


def test_r33_runtime_has_no_broker_or_order_dependency():
    source = Path(
        "services/paper_orchestration/selected_market_p6_planning_runtime.py"
    ).read_text(encoding="utf-8")

    assert "place_order(" not in source
    assert "submit_order(" not in source


def test_selected_p6_block_projects_to_exact_terminal_cycle_result():
    """Use the real selected child cycle and no fabricated P6 evidence."""
    from services.contracts.paper_orchestration_cycle_result_v1 import (
        PaperOrchestrationCycleResultV1,
    )
    from services.paper_orchestration.certified_two_market_parent_runtime import (
        run_certified_two_market_parent_runtime,
    )
    from services.contracts.two_market_decision_policy_v1 import (
        TwoMarketDecisionPolicyV1,
    )
    from services.contracts.two_market_parent_cycle_input_v1 import (
        TwoMarketParentCycleInputV1,
    )
    from services.paper_orchestration.certified_live_provider_readers import (
        CertifiedLiveProviderReaders,
    )
    from test_certified_two_market_parent_runtime import candidate_for, cycles
    from test_two_market_runtime_readiness import (
        OfflineAnalysisPipeline,
        OfflineOptionPipeline,
    )

    nifty, sensex = cycles()
    parent = TwoMarketParentCycleInputV1(
        parent_cycle_id="r33-parent", decision_result_id="r33-decision",
        nifty_child_result_id="r33-nifty", sensex_child_result_id="r33-sensex",
        nifty_observation_id=nifty.observation_id,
        sensex_observation_id=sensex.observation_id,
        requested_at=nifty.cycle_requested_at,
        completed_at=max(nifty.received_at, sensex.received_at),
        decision_policy=TwoMarketDecisionPolicyV1(180.0, 5.0),
    )
    reads = []
    def candidate(cycle, data, analysis, captured, shared_context, *, parent_cycle_id):
        reads.append(cycle.underlying_symbol)
        return candidate_for(cycle, data, score=80.0 if cycle.underlying_symbol == "NIFTY" else 60.0)
    readers = CertifiedLiveProviderReaders(
        quote_reader=lambda *_: None,
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=10_000.0,
        candidate_reader=candidate,
    )
    decision = run_certified_two_market_parent_runtime(
        parent, nifty_cycle=nifty, sensex_cycle=sensex, readers=readers,
    )
    selected = nifty if decision.selected_market == ("NIFTY", "NSE") else sensex
    planning = execute_selected_market_p6_planning(
        bridge_result_id="r33-parent-bridge", decision=decision,
        selected_cycle=selected, certified_p6_input_bundle=None,
        evaluated_at=decision.completed_at, maximum_candidate_age_seconds=180.0,
    )
    result = adapt_selected_market_p6_to_cycle_result(
        selected_cycle=selected, selected_planning=planning,
    )

    assert type(result) is PaperOrchestrationCycleResultV1
    assert reads == ["NIFTY", "SENSEX"]
    assert result.cycle_status == "BLOCKED"
    assert result.terminal_stage == "P6_PLAN"
    assert result.stage_results[0].status == "BLOCKED"
    assert result.blockers == ("CERTIFIED_P6_EVIDENCE_MISSING",)
    assert result.paper_actions == ()
    assert all(stage.stage not in {"P7_LIFECYCLE", "PERSISTENCE"} for stage in result.stage_results)
