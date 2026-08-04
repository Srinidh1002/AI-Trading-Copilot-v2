"""Connect the authoritative two-market selection to certified P6 planning.

This seam deliberately accepts an already-built ``CertifiedP6InputBundleV1``.
It does not read a provider or manufacture planning evidence: production must
retain and supply the exact typed bundle captured with the selected child.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
    CertifiedP6InputFactory,
)
from services.paper_orchestration.p6_planning_stage_executor import (
    P6PlanningStageInputV1,
    execute_p6_planning_stage,
)
from services.trade_planning.selected_market_planning_bridge import (
    bridge_selected_market_to_planning,
)
from services.paper_orchestration.stage_result_factory import (
    build_completed_stage_result,
)


P6StageAuthority = Callable[
    [P6PlanningStageInputV1], IntegratedThreeTargetTradePlanResultV1
]


@dataclass(frozen=True, slots=True)
class SelectedMarketP6PlanningResultV1:
    """Traceable PAPER terminal result for the selected-market P6 seam."""

    bridge: SelectedMarketPlanningBridgeResultV1
    planning_result: IntegratedThreeTargetTradePlanResultV1 | None
    status: str
    blockers: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if type(self.bridge) is not SelectedMarketPlanningBridgeResultV1:
            raise TypeError("bridge")
        if self.planning_result is not None and (
            type(self.planning_result) is not IntegratedThreeTargetTradePlanResultV1
        ):
            raise TypeError("planning_result")
        if self.status not in {"READY", "BLOCKED", "NO_TRADE"}:
            raise ValueError("status")
        if not isinstance(self.blockers, tuple) or not all(
            isinstance(item, str) and item.strip() for item in self.blockers
        ):
            raise ValueError("blockers")
        if self.status == "READY":
            if self.bridge.planning_allowed is not True:
                raise ValueError("READY requires planning authorization")
            if self.planning_result is None:
                raise ValueError("READY requires planning_result")
        else:
            if self.planning_result is not None:
                raise ValueError("blocked result cannot expose planning geometry")
            if not self.blockers:
                raise ValueError("blocked result requires blockers")
        if self.status == "NO_TRADE" and self.bridge.action != "NO_TRADE":
            raise ValueError("NO_TRADE requires NO_TRADE bridge")
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only result")


def _blocked(
    bridge: SelectedMarketPlanningBridgeResultV1,
    *blockers: str,
) -> SelectedMarketP6PlanningResultV1:
    return SelectedMarketP6PlanningResultV1(
        bridge=bridge,
        planning_result=None,
        status="NO_TRADE" if bridge.action == "NO_TRADE" else "BLOCKED",
        blockers=tuple(dict.fromkeys(blockers)) or ("PLANNING_NOT_ALLOWED",),
    )


def _validate_selected_cycle(
    bridge: SelectedMarketPlanningBridgeResultV1,
    cycle: PaperOrchestrationCycleInputV1,
) -> None:
    if bridge.selected_market != (cycle.underlying_symbol, cycle.exchange):
        raise ValueError("selected cycle market mismatch")
    if bridge.observation_id != cycle.observation_id:
        raise ValueError("selected cycle observation identity mismatch")


def _validate_bundle(
    bridge: SelectedMarketPlanningBridgeResultV1,
    bundle: CertifiedP6InputBundleV1,
) -> None:
    candidate = bridge.selected_candidate
    if candidate is None:
        raise ValueError("selected candidate is required")
    canonical = bundle.capital_quantity_input.canonical_trade_plan_input
    expected = (*bridge.selected_market, bridge.direction)
    if (
        canonical.underlying_symbol,
        canonical.exchange,
        getattr(canonical.selected_market_opportunity, "directional_bias", None),
    ) != expected:
        raise ValueError("P6 bundle selected market identity mismatch")
    selection = bundle.option_selection_input
    if (selection.underlying_symbol, selection.exchange, selection.direction) != expected:
        raise ValueError("P6 bundle option selection identity mismatch")
    if selection.option_right != bridge.action:
        raise ValueError("P6 bundle option right mismatch")
    if selection.option_ranking_result is not candidate.option_contract_eligibility:
        raise ValueError("P6 bundle must retain selected candidate option ranking")
    if selection.option_ranking_result_id != candidate.option_contract_eligibility.ranking_id:
        raise ValueError("P6 bundle option ranking identity mismatch")


def execute_selected_market_p6_planning(
    *,
    bridge_result_id: str,
    decision: TwoMarketDecisionResultV1,
    selected_cycle: PaperOrchestrationCycleInputV1 | None,
    certified_p6_input_bundle: CertifiedP6InputBundleV1 | None,
    evaluated_at: datetime,
    maximum_candidate_age_seconds: float,
    p6_stage_authority: P6StageAuthority = execute_p6_planning_stage,
) -> SelectedMarketP6PlanningResultV1:
    """Run P6 once, and only for the selected authoritative child.

    Missing P6 evidence is a terminal PAPER block rather than an invitation to
    reconstruct it from providers or legacy mappings.
    """
    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("decision")
    if selected_cycle is not None and type(selected_cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError("selected_cycle")
    if certified_p6_input_bundle is not None and type(certified_p6_input_bundle) is not CertifiedP6InputBundleV1:
        raise TypeError("certified_p6_input_bundle")
    if not callable(p6_stage_authority):
        raise TypeError("p6_stage_authority")

    bridge = bridge_selected_market_to_planning(
        bridge_result_id=bridge_result_id,
        decision=decision,
        evaluated_at=evaluated_at,
        maximum_candidate_age_seconds=maximum_candidate_age_seconds,
    )
    if not bridge.planning_allowed:
        return _blocked(bridge, *(bridge.blockers or ("PLANNING_NOT_ALLOWED",)))
    if selected_cycle is None:
        return _blocked(bridge, "SELECTED_P6_CYCLE_EVIDENCE_MISSING")
    if certified_p6_input_bundle is None:
        return _blocked(bridge, "CERTIFIED_P6_EVIDENCE_MISSING")

    # Identity failures are deliberate hard stops before the planner is called.
    _validate_selected_cycle(bridge, selected_cycle)
    _validate_bundle(bridge, certified_p6_input_bundle)

    factory = CertifiedP6InputFactory(
        typed_input_builder=lambda _cycle, _analysis, _opportunity: certified_p6_input_bundle,
    )
    stage_input = factory(
        selected_cycle,
        bridge.selected_candidate,
        bridge.selected_candidate.option_contract_eligibility,
    )
    planning = p6_stage_authority(stage_input)
    if type(planning) is not IntegratedThreeTargetTradePlanResultV1:
        raise TypeError("p6_stage_authority must return exact integrated result")
    if planning.status != "READY":
        return _blocked(
            bridge,
            *(tuple(planning.blockers) or ("P6_PLANNING_NOT_READY",)),
        )
    return SelectedMarketP6PlanningResultV1(
        bridge=bridge,
        planning_result=planning,
        status="READY",
    )


def adapt_selected_market_p6_to_cycle_result(
    *,
    selected_cycle: PaperOrchestrationCycleInputV1,
    selected_planning: SelectedMarketP6PlanningResultV1,
) -> PaperOrchestrationCycleResultV1:
    """Project selected-only P6 into the existing PAPER cycle-result seam.

    This is intentionally terminal at P6.  It neither creates P7/P8 inputs
    nor invokes any lifecycle, portfolio, persistence, monitoring, or broker
    authority.
    """
    if type(selected_cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError("selected_cycle")
    if type(selected_planning) is not SelectedMarketP6PlanningResultV1:
        raise TypeError("selected_planning")
    bridge = selected_planning.bridge
    if selected_planning.status != "NO_TRADE" and bridge.selected_market != (
        selected_cycle.underlying_symbol,
        selected_cycle.exchange,
    ):
        raise ValueError("selected cycle market mismatch")
    if selected_planning.status != "NO_TRADE" and bridge.observation_id != selected_cycle.observation_id:
        raise ValueError("selected cycle observation identity mismatch")

    status_map = {
        "READY": ("COMPLETED_NO_ACTION", "COMPLETED"),
        "BLOCKED": ("BLOCKED", "BLOCKED"),
        "NO_TRADE": ("COMPLETED_NO_ACTION", "NO_ACTION"),
    }
    cycle_status, stage_status = status_map[selected_planning.status]
    planning = selected_planning.planning_result
    warnings = tuple(
        dict.fromkeys(
            bridge.warnings + (() if planning is None else tuple(planning.warnings))
        )
    )
    blockers = selected_planning.blockers
    metadata = {
        "scope": "SELECTED_MARKET_P6_ONLY",
        "parent_cycle_id": bridge.parent_cycle_id,
        "parent_decision_id": bridge.parent_decision_id,
        "bridge_result_id": bridge.bridge_result_id,
        "selected_market": bridge.selected_market,
        "selected_candidate_id": bridge.candidate_id,
        "selected_child_result_id": bridge.selected_child_result_id,
        "p6_integration_id": (
            None if planning is None else planning.integration_id
        ),
    }
    stage = build_completed_stage_result(
        stage_result_id=f"{selected_cycle.cycle_id}:p6-plan:selected",
        cycle_id=selected_cycle.cycle_id,
        stage="P6_PLAN",
        started_at=selected_cycle.cycle_requested_at,
        completed_at=selected_cycle.cycle_requested_at,
        source_result=selected_planning,
        blockers=blockers,
        warnings=warnings,
        metadata=metadata,
        status=stage_status,
    )
    return PaperOrchestrationCycleResultV1(
        cycle_result_id=f"{selected_cycle.cycle_id}:selected-p6-result",
        cycle_id=selected_cycle.cycle_id,
        cycle_idempotency_key=selected_cycle.cycle_idempotency_key,
        cycle_input_semantic_hash=selected_cycle.semantic_hash(),
        cycle_status=cycle_status,
        terminal_stage="P6_PLAN",
        started_at=selected_cycle.cycle_requested_at,
        completed_at=selected_cycle.cycle_requested_at,
        stage_results=(stage,),
        paper_actions=(),
        blockers=blockers,
        warnings=warnings,
        metadata=metadata,
    )
