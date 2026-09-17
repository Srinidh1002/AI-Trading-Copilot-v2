"""Isolated market-regime orchestration facade."""
from __future__ import annotations

from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.market_regime_input_v1 import MarketRegimeInputV1
from services.contracts.market_regime_policy_v1 import DEFAULT_MARKET_REGIME_POLICY, MarketRegimePolicyV1

from .aggregate import aggregate_market_regime


def evaluate_market_regime(
    market_regime_input: MarketRegimeInputV1,
    policy: MarketRegimePolicyV1 = DEFAULT_MARKET_REGIME_POLICY,
) -> CanonicalMarketRegimeResultV1:
    """Delegate one validated normalized input to the canonical aggregator."""
    if type(market_regime_input) is not MarketRegimeInputV1:
        raise TypeError("market_regime_input")
    if type(policy) is not MarketRegimePolicyV1:
        raise TypeError("policy")
    return aggregate_market_regime(market_regime_input, policy)
