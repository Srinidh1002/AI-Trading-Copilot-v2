import pytest

from services.contracts.market_opportunity_candidate_v1 import MarketOpportunityCandidateV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.contracts.trade_opportunity_v1 import TradeOpportunityV1
from tests.fixtures.p5_12 import *


_SCENARIOS=(STRONG_BULLISH,STRONG_BEARISH,WEAK_BULLISH,WEAK_BEARISH,RANGE_BOUND,HIGH_VOLATILITY,CONFLICTING,BLOCKED,UNAVAILABLE)


@pytest.mark.parametrize('scenario',_SCENARIOS,ids=lambda scenario:scenario.scenario_name)
@pytest.mark.parametrize('identity',CANONICAL_MARKET_IDENTITIES)
def test_full_typed_stack_replays_for_every_scenario_and_market(identity,scenario):
 technical=build_technical_intelligence(identity,scenario)
 option_chain=build_option_chain_intelligence(identity,scenario)
 broader=build_broader_market_intelligence(identity,scenario)
 external=build_external_context(identity,scenario)
 regime=build_market_regime(identity,scenario,technical=technical,option_chain=option_chain,broader_market=broader,external_context=external)
 opportunity=build_trade_opportunity(identity,scenario,market_regime=regime,option_chain=option_chain)
 candidate=build_market_opportunity_candidate(identity,scenario,technical=technical,option_chain=option_chain,broader_market=broader,external_context=external,market_regime=regime,trade_opportunity=opportunity)
 assert type(technical) is TechnicalIntelligenceResultV1 and type(option_chain) is OptionChainIntelligenceResultV1
 assert type(opportunity) is TradeOpportunityV1 and type(candidate) is MarketOpportunityCandidateV1
 for value in (technical,option_chain,broader,external,regime,opportunity,candidate):
  assert (value.underlying_symbol,value.exchange)==identity
  assert value.execution_mode=='PAPER' and value.live_execution_eligible is False
 assert candidate.evaluated_at==REPLAY_EVALUATED_AT
 if scenario.blocked:assert candidate.candidate_status=='BLOCKED' and not candidate.new_entries_allowed
 if scenario.unavailable:assert candidate.candidate_status=='UNAVAILABLE' and candidate.opportunity_confidence==0.0 and not candidate.new_entries_allowed
 if scenario.conflicting:assert candidate.candidate_status=='CONFLICTING' and candidate.contradictions


@pytest.mark.parametrize('identity',CANONICAL_MARKET_IDENTITIES)
def test_strong_profiles_do_not_score_below_their_corresponding_weak_profiles(identity):
 strong_bull=build_market_opportunity_candidate(identity,STRONG_BULLISH); weak_bull=build_market_opportunity_candidate(identity,WEAK_BULLISH)
 strong_bear=build_market_opportunity_candidate(identity,STRONG_BEARISH); weak_bear=build_market_opportunity_candidate(identity,WEAK_BEARISH)
 assert strong_bull.opportunity_confidence>=weak_bull.opportunity_confidence
 assert strong_bear.opportunity_confidence>=weak_bear.opportunity_confidence
 assert strong_bull.technical_confirmation_score>=weak_bull.technical_confirmation_score
 assert strong_bear.technical_confirmation_score>=weak_bear.technical_confirmation_score
