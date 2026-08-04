"""Selected-market bridge to exact option-contract certification."""
from __future__ import annotations

from datetime import datetime

from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)
from services.contracts.selected_option_contract_certification_policy_v1 import (
    SelectedOptionContractCertificationPolicyV1,
)
from services.contracts.selected_option_contract_certification_result_v1 import (
    SelectedOptionContractCertificationResultV1,
)
from services.trade_planning.selected_option_contract_certifier import (
    certify_selected_option_contract,
)


def execute_selected_option_contract_certification(
    *,
    certification_result_id: str,
    bridge: SelectedMarketPlanningBridgeResultV1,
    policy: SelectedOptionContractCertificationPolicyV1,
    evaluated_at: datetime,
) -> SelectedOptionContractCertificationResultV1:
    """Certify exactly the contract retained by the R3.1 bridge."""

    if type(bridge) is not SelectedMarketPlanningBridgeResultV1:
        raise TypeError("bridge")
    if (
        type(policy)
        is not SelectedOptionContractCertificationPolicyV1
    ):
        raise TypeError("policy")

    return certify_selected_option_contract(
        certification_result_id=certification_result_id,
        bridge=bridge,
        evaluated_at=evaluated_at,
        maximum_ranking_age_seconds=(
            policy.maximum_ranking_age_seconds
        ),
        maximum_contract_age_seconds=(
            policy.maximum_contract_age_seconds
        ),
        maximum_quote_age_seconds=(
            policy.maximum_quote_age_seconds
        ),
        maximum_spread_fraction=(
            policy.maximum_spread_fraction
        ),
        minimum_liquidity_score=(
            policy.minimum_liquidity_score
        ),
        minimum_open_interest=(
            policy.minimum_open_interest
        ),
        minimum_volume=policy.minimum_volume,
    )
