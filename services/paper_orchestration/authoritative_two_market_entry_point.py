"""Single authoritative live two-market PAPER entry point."""
from __future__ import annotations

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
