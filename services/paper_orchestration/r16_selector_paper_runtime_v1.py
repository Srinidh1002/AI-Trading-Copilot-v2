"""R16 selector-based PAPER composition over existing certified P6/P7/P8.

The parent selector always runs as an observational decision first.  PAPER
entry can proceed only when the separate R16 activation authority is READY.
The incumbent R15 campaign therefore cannot be overlapped accidentally.

No live-order or broker-submission authority exists in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.analysis.live_market_candidate_evaluator import (
    LiveMarketCandidateEvaluationResultV1,
)
from services.certification.task9_selected_market_lifecycle_runtime import (
    execute_task9_selected_market_lifecycle,
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
from services.paper_orchestration.r16_canonical_candidate_reader_v1 import (
    R16CanonicalCandidateReaderV1,
)
from services.paper_orchestration.r16_strategy_authority_v1 import (
    R16_STATE_NAMESPACE,
    R16SelectorActivationStatusV1,
    evaluate_r16_selector_activation,
)
from services.paper_orchestration.r16_two_market_shadow_source_v1 import (
    R16TwoMarketShadowCycleV1,
    R16TwoMarketShadowSourceV1,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    SelectedMarketP6PlanningResultV1,
    execute_selected_market_p6_planning,
)
from services.trade_planning.selected_market_planning_bridge import (
    bridge_selected_market_to_planning,
)
from services.trade_planning.task9_selected_market_p6_bundle import (
    build_task9_selected_market_p6_bundle,
)


@dataclass(frozen=True, slots=True)
class R16SelectorPaperRuntimeResultV1:
    status: str
    shadow_cycle: R16TwoMarketShadowCycleV1
    activation: R16SelectorActivationStatusV1
    bridge: SelectedMarketPlanningBridgeResultV1
    selected_cycle: PaperOrchestrationCycleInputV1 | None = None
    selected_evaluation: LiveMarketCandidateEvaluationResultV1 | None = None
    planning: SelectedMarketP6PlanningResultV1 | None = None
    lifecycle: PaperOrchestrationCycleResultV1 | None = None
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        allowed = {
            "NO_TRADE",
            "SHADOW_SELECTED",
            "PLANNING_BLOCKED",
            "PAPER_LIFECYCLE",
        }
        if self.status not in allowed:
            raise ValueError("status")
        if type(self.shadow_cycle) is not R16TwoMarketShadowCycleV1:
            raise TypeError("shadow_cycle")
        if type(self.activation) is not R16SelectorActivationStatusV1:
            raise TypeError("activation")
        if type(self.bridge) is not SelectedMarketPlanningBridgeResultV1:
            raise TypeError("bridge")
        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("R16 runtime must remain PAPER-only")
        if self.status in {"NO_TRADE", "SHADOW_SELECTED"}:
            if self.planning is not None or self.lifecycle is not None:
                raise ValueError("non-entry result cannot expose lifecycle")
        if self.status == "PAPER_LIFECYCLE":
            if (
                self.selected_cycle is None
                or self.selected_evaluation is None
                or self.planning is None
                or self.lifecycle is None
            ):
                raise ValueError("PAPER_LIFECYCLE requires complete trace")
            if not self.activation.ready:
                raise ValueError("lifecycle requires ready activation")


def _selected_cycle(
    shadow: R16TwoMarketShadowCycleV1,
) -> PaperOrchestrationCycleInputV1 | None:
    selected = shadow.decision.selected_market
    if selected is None:
        return None
    if selected == ("NIFTY", "NSE"):
        return shadow.nifty_cycle
    if selected == ("SENSEX", "BSE"):
        return shadow.sensex_cycle
    raise ValueError("unsupported selected market")


def execute_r16_selector_paper_cycle(
    *,
    source: R16TwoMarketShadowSourceV1,
    repo_root: str | Path,
    incumbent_runtime_root: str | Path | None,
    available_capital: float,
    evaluated_at: datetime,
    maximum_candidate_age_seconds: float = 180.0,
    risk_fraction: float = 0.01,
    maximum_quantity: int | None = None,
) -> R16SelectorPaperRuntimeResultV1:
    """Run one selector cycle with fail-closed R16 PAPER activation.

    In the default SHADOW_ONLY mode the function stops immediately after
    selection/bridge and performs no P6/P7/P8 persistence.
    """

    if type(source) is not R16TwoMarketShadowSourceV1:
        raise TypeError("source")
    if (
        not isinstance(evaluated_at, datetime)
        or evaluated_at.tzinfo is None
        or evaluated_at.utcoffset() is None
    ):
        raise ValueError("evaluated_at")

    shadow = source.run_shadow_cycle()
    activation = evaluate_r16_selector_activation(
        repo_root=repo_root,
        incumbent_runtime_root=incumbent_runtime_root,
    )
    bridge_id = f"{shadow.parent.parent_cycle_id}:r16-planning-bridge"
    bridge = bridge_selected_market_to_planning(
        bridge_result_id=bridge_id,
        decision=shadow.decision,
        evaluated_at=evaluated_at,
        maximum_candidate_age_seconds=maximum_candidate_age_seconds,
    )

    if shadow.decision.decision == "NO_TRADE":
        return R16SelectorPaperRuntimeResultV1(
            status="NO_TRADE",
            shadow_cycle=shadow,
            activation=activation,
            bridge=bridge,
        )

    selected_cycle = _selected_cycle(shadow)
    if selected_cycle is None:
        raise ValueError("selected parent decision has no selected cycle")

    # The parent comparison is useful in SHADOW even when entry is prohibited.
    if not activation.ready:
        return R16SelectorPaperRuntimeResultV1(
            status="SHADOW_SELECTED",
            shadow_cycle=shadow,
            activation=activation,
            bridge=bridge,
            selected_cycle=selected_cycle,
        )

    candidate_reader = source.readers.candidate_reader
    if type(candidate_reader) is not R16CanonicalCandidateReaderV1:
        raise TypeError("R16 canonical candidate reader required")

    selected_market = selected_cycle.underlying_symbol
    evaluation = candidate_reader.get_evaluation(
        parent_cycle_id=shadow.parent.parent_cycle_id,
        market=selected_market,
    )
    if type(evaluation) is not LiveMarketCandidateEvaluationResultV1:
        raise RuntimeError("SELECTED_EVALUATION_NOT_RETAINED")

    bundle = build_task9_selected_market_p6_bundle(
        bridge=bridge,
        cycle=selected_cycle,
        evaluation=evaluation,
        available_capital=float(available_capital),
        evaluated_at=evaluated_at,
        risk_fraction=risk_fraction,
        maximum_quantity=maximum_quantity,
    )

    planning = execute_selected_market_p6_planning(
        bridge_result_id=bridge_id,
        decision=shadow.decision,
        selected_cycle=selected_cycle,
        certified_p6_input_bundle=bundle,
        evaluated_at=evaluated_at,
        maximum_candidate_age_seconds=maximum_candidate_age_seconds,
    )

    if planning.status != "READY":
        return R16SelectorPaperRuntimeResultV1(
            status="PLANNING_BLOCKED",
            shadow_cycle=shadow,
            activation=activation,
            bridge=bridge,
            selected_cycle=selected_cycle,
            selected_evaluation=evaluation,
            planning=planning,
        )

    persistence_root = (
        Path(repo_root).resolve()
        / R16_STATE_NAMESPACE
        / "runtime"
    )
    lifecycle = execute_task9_selected_market_lifecycle(
        selected_cycle=selected_cycle,
        selected_planning=planning,
        available_capital=float(available_capital),
        evaluated_at=evaluated_at,
        persistence_root=persistence_root,
        portfolio_id="r16-selector-paper-portfolio",
    )

    return R16SelectorPaperRuntimeResultV1(
        status="PAPER_LIFECYCLE",
        shadow_cycle=shadow,
        activation=activation,
        bridge=bridge,
        selected_cycle=selected_cycle,
        selected_evaluation=evaluation,
        planning=planning,
        lifecycle=lifecycle,
    )
