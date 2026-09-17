"""Provider-free fixed fixture profiles for Task 2E2 certification."""
from services.contracts.task2_decision_certification_fixture_v1 import Task2MarketFixtureV1,Task2TwoMarketFixtureV1
from dataclasses import replace
from pathlib import Path
import sys

PILLAR_ORDER=("price_action","candlestick","chart_pattern","volume","volatility","oi","oi_change","pcr","support_resistance","max_pain","iv","greeks","premium_behavior","liquidity_spread")

def build_candidate(item):
 """Reuse the repository's provider-free typed-candidate fixture builder.

 The E2 foundation deliberately exercises the production action/ranking and
 explanation boundaries without introducing a second evidence/scoring engine.
 """
 tests_path=str(Path(__file__).resolve().parents[2]/"tests")
 if tests_path not in sys.path:sys.path.insert(0,tests_path)
 from test_market_analysis_candidate_v1 import build, unavailable_candidate
 base=dict(underlying_symbol=item.underlying_symbol,candidate_id=item.candidate_id,observation_id=item.observation_id,warnings=item.controlled_warnings,blockers=item.controlled_blockers,contradictions=item.controlled_contradictions)
 if item.fixture_profile_id in {"UNAVAILABLE_CHILD","REQUIRED_EVIDENCE_MISSING"}: return unavailable_candidate(**base)
 if item.fixture_profile_id in {"CONFLICTING_CHILD","REGIME_BLOCKED"}:
  return unavailable_candidate(**base)
 if item.fixture_profile_id=="ELIGIBLE_BEARISH": return build(**base,direction="BEARISH",eligibility="ELIGIBLE",confidence=item.candidate_confidence,score=item.candidate_score)
 if item.fixture_profile_id=="ELIGIBLE_BULLISH": return build(**base,direction="BULLISH",eligibility="ELIGIBLE",confidence=item.candidate_confidence,score=item.candidate_score)
 return build(**base,direction="NEUTRAL",eligibility="INELIGIBLE",confidence=item.candidate_confidence,score=item.candidate_score)

def build_canonical_sources(item):
 """Return fixed, provider-free canonical sources accepted by Task 2A/2B."""
 tests_path=str(Path(__file__).resolve().parents[2]/"tests")
 if tests_path not in sys.path:sys.path.insert(0,tests_path)
 from test_task8_parent_typed_candidate_certification import captured,NOW
 from services.market_session.validator import validate_session_timestamp
 from services.analysis.live_market_candidate_evaluator import LiveCandidatePolicySourceV1,evaluate_captured_certified_market_candidate
 from services.analysis.live_canonical_engine_adapters import build_default_live_canonical_evidence_engines
 value=captured(item.underlying_symbol,item.exchange,25000.0 if item.underlying_symbol=="NIFTY" else 80000.0,complete_options=True)
 session=validate_session_timestamp(symbol=item.underlying_symbol,exchange=item.exchange,market_timestamp=NOW,evaluated_at=NOW,validation_mode="LENIENT_ANALYSIS",id_factory=lambda:f"session:{item.observation_id}")
 policy=LiveCandidatePolicySourceV1(item.candidate_direction,item.candidate_eligibility,item.candidate_confidence,item.candidate_score,blockers=item.controlled_blockers,warnings=item.controlled_warnings,contradictions=item.controlled_contradictions)
 return evaluate_captured_certified_market_candidate(captured_evidence=value,session_validation=session,policy_source=policy,parent_cycle_id=item.parent_cycle_id,candidate_id=item.candidate_id,observation_id=item.observation_id,engines=build_default_live_canonical_evidence_engines()),policy
def market_fixture(*,profile,underlying_symbol,exchange,parent_cycle_id,observation_id,candidate_id,evaluated_at):
 action={"ELIGIBLE_BULLISH":"CALL","ELIGIBLE_BEARISH":"PUT"}.get(profile,"WAIT")
 direction={"ELIGIBLE_BULLISH":"BULLISH","ELIGIBLE_BEARISH":"BEARISH"}.get(profile,"UNAVAILABLE" if profile in {"UNAVAILABLE_CHILD","CONFLICTING_CHILD","REQUIRED_EVIDENCE_MISSING","REGIME_BLOCKED"} else "NEUTRAL")
 eligible=profile in {"ELIGIBLE_BULLISH","ELIGIBLE_BEARISH"}
 blocker=() if eligible or profile in {"VALID_WAIT","OPTIONAL_EXTERNAL_UNAVAILABLE"} else (profile,)
 return Task2MarketFixtureV1(profile,underlying_symbol,exchange,parent_cycle_id,observation_id,candidate_id,evaluated_at,direction,"ELIGIBLE" if eligible else "INELIGIBLE",75.0 if eligible else 50.0,75.0 if eligible else 50.0,"SUITABLE" if eligible else "UNAVAILABLE",profile,"COMPLETED" if profile not in {"UNAVAILABLE_CHILD","REQUIRED_EVIDENCE_MISSING"} else "UNAVAILABLE",blocker,("OPTIONAL_EXTERNAL_UNAVAILABLE",) if profile=="OPTIONAL_EXTERNAL_UNAVAILABLE" else (),(),action,"COMPLETED" if profile not in {"UNAVAILABLE_CHILD","REQUIRED_EVIDENCE_MISSING"} else "UNAVAILABLE","READY" if profile not in {"UNAVAILABLE_CHILD","REQUIRED_EVIDENCE_MISSING"} else "UNAVAILABLE",profile not in {"UNAVAILABLE_CHILD","REQUIRED_EVIDENCE_MISSING"})
def foundation_fixtures(evaluated_at):
 def make(scenario,np,sp,selected,action):
  parent=f"parent:{scenario}"
  return Task2TwoMarketFixtureV1(scenario,parent,evaluated_at,market_fixture(profile=np,underlying_symbol="NIFTY",exchange="NSE",parent_cycle_id=parent,observation_id=f"observation:{scenario}:nifty",candidate_id=f"candidate:{scenario}:nifty",evaluated_at=evaluated_at),market_fixture(profile=sp,underlying_symbol="SENSEX",exchange="BSE",parent_cycle_id=parent,observation_id=f"observation:{scenario}:sensex",candidate_id=f"candidate:{scenario}:sensex",evaluated_at=evaluated_at),selected,action,"SELECTED" if selected!="NONE" else "NO_TRADE","VALID")
 return (make("FOUNDATION_NIFTY_CALL","ELIGIBLE_BULLISH","VALID_WAIT","NIFTY","CALL"),make("FOUNDATION_SENSEX_PUT","VALID_WAIT","ELIGIBLE_BEARISH","SENSEX","PUT"),make("FOUNDATION_NO_TRADE","VALID_WAIT","VALID_WAIT","NONE","NO_TRADE"),make("FOUNDATION_UNAVAILABLE","REQUIRED_EVIDENCE_MISSING","UNAVAILABLE_CHILD","NONE","NO_TRADE"),make("FOUNDATION_OPTIONAL_WARNING","OPTIONAL_EXTERNAL_UNAVAILABLE","VALID_WAIT","NONE","NO_TRADE"))
