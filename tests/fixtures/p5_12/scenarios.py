from dataclasses import dataclass
from types import MappingProxyType
_COMPONENTS=('technical','option_chain','broader_market','external_context','market_regime','trade_opportunity','liquidity','execution_quality')
_QUALITY={'PRESENT_GOOD','PRESENT_PARTIAL','PRESENT_DEGRADED','MISSING_OPTIONAL','MISSING_REQUIRED','PROVIDER_BLOCKED_OPTIONAL','PROVIDER_BLOCKED_REQUIRED','UNAVAILABLE_OPTIONAL','UNAVAILABLE_REQUIRED'}
@dataclass(frozen=True)
class FullIntelligenceScenarioV1:
 scenario_name:str;direction:str='RANGE_BOUND';strength:str='MODERATE';regime_state:str='RANGE_BOUND';quality_state:str='GOOD';freshness_state:str='FRESH';event_state:str='NONE';session_state:str='REGULAR';blocked:bool=False;unavailable:bool=False;conflicting:bool=False;warning:bool=False;missing_optional_components:tuple[str,...]=();missing_required_components:tuple[str,...]=();provider_blocked_components:tuple[str,...]=();notes:tuple[str,...]=()
STRONG_BULLISH=FullIntelligenceScenarioV1('STRONG_BULLISH','STRONG_BULLISH','STRONG','STRONG_BULLISH')
STRONG_BEARISH=FullIntelligenceScenarioV1('STRONG_BEARISH','STRONG_BEARISH','STRONG','STRONG_BEARISH')
WEAK_BULLISH=FullIntelligenceScenarioV1('WEAK_BULLISH','WEAK_BULLISH','WEAK','BULLISH')
WEAK_BEARISH=FullIntelligenceScenarioV1('WEAK_BEARISH','WEAK_BEARISH','WEAK','BEARISH')
RANGE_BOUND=FullIntelligenceScenarioV1('RANGE_BOUND')
HIGH_VOLATILITY=FullIntelligenceScenarioV1('HIGH_VOLATILITY','HIGH_VOLATILITY','MODERATE','HIGH_VOLATILITY')
CONFLICTING=FullIntelligenceScenarioV1('CONFLICTING','CONFLICTING','NONE','CONFLICTING',conflicting=True)
BLOCKED=FullIntelligenceScenarioV1('BLOCKED','BLOCKED','NONE','BLOCKED',blocked=True)
UNAVAILABLE=FullIntelligenceScenarioV1('UNAVAILABLE','UNAVAILABLE','NONE','UNAVAILABLE',quality_state='UNAVAILABLE',freshness_state='UNAVAILABLE',unavailable=True)
FRESH=FullIntelligenceScenarioV1('FRESH');DELAYED=FullIntelligenceScenarioV1('DELAYED',freshness_state='DELAYED');STALE=FullIntelligenceScenarioV1('STALE',freshness_state='STALE');FUTURE=FullIntelligenceScenarioV1('FUTURE',freshness_state='FUTURE')
PARTIAL_OPTIONAL=FullIntelligenceScenarioV1('PARTIAL_OPTIONAL',missing_optional_components=('OPTION_CHAIN',));MISSING_REQUIRED=FullIntelligenceScenarioV1('MISSING_REQUIRED',missing_required_components=('TECHNICAL',));PROVIDER_BLOCKED=FullIntelligenceScenarioV1('PROVIDER_BLOCKED',blocked=True,provider_blocked_components=('EXTERNAL_CONTEXT',));MIXED_TIMESTAMPS=FullIntelligenceScenarioV1('MIXED_TIMESTAMPS',freshness_state='MIXED')
RBI_BLOCK=FullIntelligenceScenarioV1('RBI_BLOCK',event_state='RBI_BLOCK')
UNION_BUDGET=FullIntelligenceScenarioV1('UNION_BUDGET',event_state='UNION_BUDGET')
CPI_WARNING=FullIntelligenceScenarioV1('CPI_WARNING',event_state='CPI_WARNING',warning=True)
ELECTION_EVENT=FullIntelligenceScenarioV1('ELECTION_EVENT',event_state='ELECTION_EVENT',warning=True)
HOLIDAY=FullIntelligenceScenarioV1('HOLIDAY',session_state='HOLIDAY',blocked=True)
SPECIAL_SESSION=FullIntelligenceScenarioV1('SPECIAL_SESSION',session_state='SPECIAL_SESSION',warning=True)
WEEKLY_EXPIRY=FullIntelligenceScenarioV1('WEEKLY_EXPIRY',event_state='WEEKLY_EXPIRY',warning=True)
MONTHLY_EXPIRY=FullIntelligenceScenarioV1('MONTHLY_EXPIRY',event_state='MONTHLY_EXPIRY',warning=True)
ROLLOVER=FullIntelligenceScenarioV1('ROLLOVER',event_state='ROLLOVER',warning=True)
OVERLAPPING_EVENTS=FullIntelligenceScenarioV1('OVERLAPPING_EVENTS',event_state='OVERLAPPING_EVENTS',warning=True)
EVENT_PLUS_SESSION_RESTRICTION=FullIntelligenceScenarioV1('EVENT_PLUS_SESSION_RESTRICTION',event_state='CPI_WARNING',session_state='HOLIDAY',blocked=True)

def describe_missing_required_components(scenario):
 """Return a safe evaluator-boundary descriptor; it never constructs an invalid candidate."""
 return MappingProxyType({'missing_required_components':tuple(scenario.missing_required_components),'fails_closed':bool(scenario.missing_required_components)})

@dataclass(frozen=True)
class ComponentQualityProfileV1:
 technical:str='PRESENT_GOOD';option_chain:str='PRESENT_GOOD';broader_market:str='PRESENT_GOOD';external_context:str='PRESENT_GOOD';market_regime:str='PRESENT_GOOD';trade_opportunity:str='PRESENT_GOOD';liquidity:str='PRESENT_GOOD';execution_quality:str='PRESENT_GOOD'
 def __post_init__(self):
  for component in _COMPONENTS:
   if getattr(self,component) not in _QUALITY:raise ValueError('component quality state')
 def to_dict(self):return {component:getattr(self,component) for component in _COMPONENTS}

COMPLETE_GOOD_PROFILE=ComponentQualityProfileV1()
PARTIAL_OPTIONAL_PROFILE=ComponentQualityProfileV1(option_chain='PRESENT_PARTIAL',broader_market='PRESENT_PARTIAL',external_context='PRESENT_PARTIAL')
MISSING_OPTIONAL_PROFILE=ComponentQualityProfileV1(option_chain='MISSING_OPTIONAL')
MISSING_REQUIRED_PROFILE=ComponentQualityProfileV1(technical='MISSING_REQUIRED')
OPTIONAL_PROVIDER_BLOCKED_PROFILE=ComponentQualityProfileV1(external_context='PROVIDER_BLOCKED_OPTIONAL')
REQUIRED_PROVIDER_BLOCKED_PROFILE=ComponentQualityProfileV1(technical='PROVIDER_BLOCKED_REQUIRED')

@dataclass(frozen=True)
class MissingRequiredEvaluationCaseV1:
 baseline_candidate:object;missing_component:str;expected_eligibility_state:str='BLOCKED';expected_blocker:str='MISSING_REQUIRED_REFERENCE'
 def evaluator_result_kwargs(self):return MappingProxyType({'eligibility_state':self.expected_eligibility_state,'rankable':False,'blockers':(self.expected_blocker,),'missing_required_reference':True})
 def evaluator_patch(self,original):
  def evaluate(candidate,policy):
   if candidate is not self.baseline_candidate:return original(candidate,policy)
   from services.opportunity_ranking.eligibility import CandidateEligibilityEvaluationV1
   return CandidateEligibilityEvaluationV1(candidate.underlying_symbol,candidate.exchange,self.expected_eligibility_state,False,(self.expected_blocker,),missing_required_reference=True,analysis_allowed=candidate.analysis_allowed,new_entries_allowed=candidate.new_entries_allowed)
  return evaluate
