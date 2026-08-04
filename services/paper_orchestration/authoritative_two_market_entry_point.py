"""Single authoritative live two-market PAPER entry point."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_two_market_parent_runtime import (
    run_certified_two_market_parent_runtime,
)
from services.paper_orchestration.certified_p6_input_factory import (
    CertifiedP6InputBundleV1,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    P6StageAuthority,
    SelectedMarketP6PlanningResultV1,
    execute_selected_market_p6_planning,
)


AUTHORITATIVE_TWO_MARKET_ENTRY_POINT_ID = (
    "CERTIFIED_TWO_MARKET_PARENT_RUNTIME_V1"
)


def run_authoritative_two_market_parent_cycle(
    parent: TwoMarketParentCycleInputV1,
    *,
    nifty_cycle: PaperOrchestrationCycleInputV1,
    sensex_cycle: PaperOrchestrationCycleInputV1,
    readers: CertifiedLiveProviderReaders,
    substage_callback=None,
) -> TwoMarketDecisionResultV1:
    """Execute the only approved live NIFTY/SENSEX PAPER parent path."""

    if type(parent) is not TwoMarketParentCycleInputV1:
        raise TypeError("parent")
    if type(nifty_cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError("nifty_cycle")
    if type(sensex_cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError("sensex_cycle")
    if type(readers) is not CertifiedLiveProviderReaders:
        raise TypeError("readers")

    if parent.execution_mode != "PAPER":
        raise ValueError("parent must remain PAPER")
    if parent.live_execution_eligible:
        raise ValueError("parent cannot be live eligible")
    if parent.broker_order_submission:
        raise ValueError("broker order submission must remain disabled")

    return run_certified_two_market_parent_runtime(
        parent,
        nifty_cycle=nifty_cycle,
        sensex_cycle=sensex_cycle,
        readers=readers,
        substage_callback=substage_callback,
    )


def run_authoritative_two_market_selected_p6_cycle(
    parent: TwoMarketParentCycleInputV1,
    *,
    nifty_cycle: PaperOrchestrationCycleInputV1,
    sensex_cycle: PaperOrchestrationCycleInputV1,
    readers: CertifiedLiveProviderReaders,
    bridge_result_id: str,
    evaluated_at: datetime,
    maximum_candidate_age_seconds: float,
    certified_p6_input_bundles: Mapping[tuple[str, str], CertifiedP6InputBundleV1],
    p6_stage_authority: P6StageAuthority | None = None,
    substage_callback=None,
) -> SelectedMarketP6PlanningResultV1:
    """Run the parent once, then route only its selected child into P6.

    Bundles are caller-retained typed evidence.  The selected lookup happens
    only after ranking, so the losing market's planning bundle is never read
    and its planner is never invoked.
    """
    if not isinstance(certified_p6_input_bundles, Mapping):
        raise TypeError("certified_p6_input_bundles")
    decision = run_authoritative_two_market_parent_cycle(
        parent,
        nifty_cycle=nifty_cycle,
        sensex_cycle=sensex_cycle,
        readers=readers,
        substage_callback=substage_callback,
    )
    cycles = {
        (nifty_cycle.underlying_symbol, nifty_cycle.exchange): nifty_cycle,
        (sensex_cycle.underlying_symbol, sensex_cycle.exchange): sensex_cycle,
    }
    selected_market = decision.selected_market
    selected_cycle = cycles.get(selected_market) if selected_market else None
    bundle = (
        certified_p6_input_bundles.get(selected_market)
        if selected_market is not None
        else None
    )
    kwargs = {}
    if p6_stage_authority is not None:
        kwargs["p6_stage_authority"] = p6_stage_authority
    return execute_selected_market_p6_planning(
        bridge_result_id=bridge_result_id,
        decision=decision,
        selected_cycle=selected_cycle,
        certified_p6_input_bundle=bundle,
        evaluated_at=evaluated_at,
        maximum_candidate_age_seconds=maximum_candidate_age_seconds,
        **kwargs,
    )
