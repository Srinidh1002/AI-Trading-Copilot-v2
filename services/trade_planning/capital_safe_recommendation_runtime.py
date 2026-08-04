"""Task 4 end-to-end PAPER recommendation runtime with an injected certified P6 seam."""
from __future__ import annotations

from collections.abc import Callable

from services.contracts.capital_risk_authority_v1 import (
    CapitalRiskAuthorityInputV1,
)
from services.contracts.final_trade_recommendation_v1 import (
    FinalTradeRecommendationV1,
)
from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.trade_planning.capital_risk_authority import (
    evaluate_capital_risk_authority,
)
from services.trade_planning.final_trade_recommendation_projector import (
    project_final_trade_recommendation,
)
from services.trade_planning.selected_market_planning_bridge import (
    bridge_selected_market_to_planning,
)


CertifiedP6Planner = Callable[
    [
        object,
        object,
    ],
    IntegratedThreeTargetTradePlanResultV1,
]


def run_capital_safe_recommendation_cycle(
    *,
    bridge_result_id: str,
    authority_result_id: str,
    recommendation_id: str,
    decision: TwoMarketDecisionResultV1,
    capital_risk_input: CapitalRiskAuthorityInputV1,
    maximum_candidate_age_seconds: float,
    certified_p6_planner: CertifiedP6Planner,
) -> FinalTradeRecommendationV1:
    """Run Task 4 from Task 3 decision through final recommendation."""

    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("decision")
    if type(capital_risk_input) is not CapitalRiskAuthorityInputV1:
        raise TypeError("capital_risk_input")
    if not callable(certified_p6_planner):
        raise TypeError("certified_p6_planner")

    bridge = bridge_selected_market_to_planning(
        bridge_result_id=bridge_result_id,
        decision=decision,
        evaluated_at=capital_risk_input.evaluated_at,
        maximum_candidate_age_seconds=maximum_candidate_age_seconds,
    )
    authority = evaluate_capital_risk_authority(
        authority_result_id=authority_result_id,
        authority_input=capital_risk_input,
    )

    if bridge.action == "NO_TRADE":
        planning = certified_p6_planner(bridge, authority)
        if type(planning) is not IntegratedThreeTargetTradePlanResultV1:
            raise TypeError(
                "certified_p6_planner must return exact integrated result"
            )
        return project_final_trade_recommendation(
            recommendation_id=recommendation_id,
            bridge=bridge,
            authority=authority,
            planning=planning,
        )

    if bridge.selected_market != capital_risk_input.selected_market:
        raise ValueError(
            "capital authority input must match selected market"
        )

    planning = certified_p6_planner(bridge, authority)
    if type(planning) is not IntegratedThreeTargetTradePlanResultV1:
        raise TypeError(
            "certified_p6_planner must return exact integrated result"
        )

    return project_final_trade_recommendation(
        recommendation_id=recommendation_id,
        bridge=bridge,
        authority=authority,
        planning=planning,
    )
