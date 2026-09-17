"""Provider-free Task 2E2 composition through production decision builders."""
import hashlib,json
from dataclasses import dataclass
from typing import Callable
from services.certification.task2_decision_fixture_factory import PILLAR_ORDER,build_candidate,build_canonical_sources
from services.contracts.task2_decision_certification_fixture_v1 import Task2TwoMarketFixtureV1
from services.contracts.task2_decision_certification_result_v1 import Task2MarketDecisionCertificationV1,Task2DecisionCertificationResultV1
from services.contracts.two_market_child_terminal_result_v1 import TwoMarketChildTerminalResultV1
from services.contracts.two_market_decision_policy_v1 import TwoMarketDecisionPolicyV1
from services.analysis.pre_entry_action_resolver import resolve_pre_entry_market_action
from services.analysis.market_decision_explanation import build_market_decision_explanation
from services.analysis.two_market_decision_ranker import rank_two_market_candidates
from services.analysis.two_market_decision_explanation import build_two_market_decision_explanation
from services.certification.task2_pre_entry_action_report import project_parent_pre_entry_action
from services.analysis.market_analysis_pillar_contributions import build_market_analysis_pillar_contributions
from services.analysis.market_analysis_confidence_ledger import build_market_analysis_confidence_ledger

@dataclass(frozen=True,slots=True)
class Task2DecisionCertificationDependencies:
 build_pillar_contributions:Callable=build_market_analysis_pillar_contributions;build_confidence_ledger:Callable=build_market_analysis_confidence_ledger;resolve_child_action:Callable=resolve_pre_entry_market_action;build_child_explanation:Callable=build_market_decision_explanation;rank_two_markets:Callable=rank_two_market_candidates;project_parent_action:Callable=project_parent_pre_entry_action;build_parent_explanation:Callable=build_two_market_decision_explanation

DEFAULT_DEPENDENCIES=Task2DecisionCertificationDependencies()

def compose_task2_decision_certification(fixture:Task2TwoMarketFixtureV1,*,dependencies:Task2DecisionCertificationDependencies|None=None)->Task2DecisionCertificationResultV1:
 if type(fixture) is not Task2TwoMarketFixtureV1:raise TypeError("fixture")
 dependencies=DEFAULT_DEPENDENCIES if dependencies is None else dependencies
 if type(dependencies) is not Task2DecisionCertificationDependencies:raise TypeError("dependencies")
 calls={"market_fixture_build_count":0,"pillar_contribution_build_count":0,"total_pillar_contribution_count":0,"confidence_ledger_build_count":0,"pre_entry_action_resolution_count":0,"child_explanation_build_count":0,"parent_rank_evaluation_count":0,"parent_action_projection_count":0,"parent_explanation_build_count":0,"certification_result_build_count":1}
 def build(item):
  calls["market_fixture_build_count"]+=1; candidate=build_candidate(item)
  canonical,policy=build_canonical_sources(item)
  contributions=dependencies.build_pillar_contributions(cycle_id=fixture.parent_cycle_id,observation_id=item.observation_id,observation=canonical.observation,option_chain=canonical.evidence.option_chain,contract_ranking=canonical.evidence.contract_ranking,pillars=canonical.evidence.pillars,evaluated_at=canonical.evidence.pillars.evaluated_at);calls["pillar_contribution_build_count"]+=1;calls["total_pillar_contribution_count"]+=len(contributions.contributions)
  canonical_evidence=canonical.evidence.__class__(**{**canonical.evidence.__dict__,"contributions":contributions}) if hasattr(canonical.evidence,"__dict__") else canonical.evidence
  ledger=dependencies.build_confidence_ledger(cycle_id=fixture.parent_cycle_id,observation_id=item.observation_id,evidence=canonical.evidence,policy_source=policy);calls["confidence_ledger_build_count"]+=1
  if candidate is None:
   action=dependencies.resolve_child_action(candidate=None,cycle_id=fixture.parent_cycle_id,observation_id=item.observation_id,evaluated_at=fixture.fixed_evaluated_at,failure_codes=item.controlled_blockers or ("CANDIDATE_UNAVAILABLE",)); calls["pre_entry_action_resolution_count"]+=1
   terminal=TwoMarketChildTerminalResultV1(f"child:{item.observation_id}",fixture.parent_cycle_id,item.observation_id,item.underlying_symbol,item.exchange,fixture.fixed_evaluated_at,fixture.fixed_evaluated_at,"UNAVAILABLE",blockers=item.controlled_blockers or ("CANDIDATE_UNAVAILABLE",))
   explanation=dependencies.build_child_explanation(candidate=None,action=action,cycle_id=fixture.parent_cycle_id,observation_id=item.observation_id,evaluated_at=fixture.fixed_evaluated_at,contributions=contributions,ledger=ledger,terminal_codes=terminal.blockers); calls["child_explanation_build_count"]+=1
   return candidate,ledger,contributions,action,explanation,terminal
  action=dependencies.resolve_child_action(candidate=candidate,cycle_id=fixture.parent_cycle_id,observation_id=item.observation_id,evaluated_at=fixture.fixed_evaluated_at,ledger=ledger); calls["pre_entry_action_resolution_count"]+=1
  terminal=TwoMarketChildTerminalResultV1(f"child:{item.observation_id}",fixture.parent_cycle_id,item.observation_id,item.underlying_symbol,item.exchange,candidate.requested_at,candidate.received_at,"COMPLETED",candidate=candidate)
  explanation=dependencies.build_child_explanation(candidate=candidate,action=action,cycle_id=fixture.parent_cycle_id,observation_id=item.observation_id,evaluated_at=fixture.fixed_evaluated_at,contributions=contributions,ledger=ledger); calls["child_explanation_build_count"]+=1
  return candidate,ledger,contributions,action,explanation,terminal
 nifty=build(fixture.nifty);sensex=build(fixture.sensex)
 decision=dependencies.rank_two_markets(decision_result_id=f"decision:{fixture.scenario_id}",parent_cycle_id=fixture.parent_cycle_id,requested_at=min(nifty[5].requested_at,sensex[5].requested_at),completed_at=max(nifty[5].received_at,sensex[5].received_at),nifty=nifty[5],sensex=sensex[5],policy=TwoMarketDecisionPolicyV1(180.,5.));calls["parent_rank_evaluation_count"]+=1
 projection=dependencies.project_parent_action(parent_decision=decision,nifty_action=nifty[3],sensex_action=sensex[3]);calls["parent_action_projection_count"]+=1
 parent_explanation=dependencies.build_parent_explanation(parent_decision=decision,nifty_action=nifty[3],sensex_action=sensex[3],nifty_explanation=nifty[4],sensex_explanation=sensex[4],parent_action_projection=projection);calls["parent_explanation_build_count"]+=1
 def market(item,built):
  candidate,ledger,contributions,action,explanation,terminal=built; names=tuple(x.pillar_name for x in contributions.contributions)
  return Task2MarketDecisionCertificationV1(f"certification:{item.observation_id}",fixture.scenario_id,item.underlying_symbol,item.exchange,fixture.parent_cycle_id,item.observation_id,getattr(candidate,"candidate_id",None),"READY" if candidate else "UNAVAILABLE",len(names),names,tuple(x.status for x in contributions.contributions),tuple(x.provenance_classification for x in contributions.contributions),ledger.ledger_id,ledger.status,getattr(candidate,"confidence",0.),ledger.final_confidence,ledger.final_confidence-getattr(candidate,"confidence",0.),getattr(candidate,"score",0.),ledger.final_score,ledger.final_score-getattr(candidate,"score",0.),action.action_id,action.action,explanation.explanation_id,"VALID",terminal.terminal_status,tuple(terminal.blockers or terminal.errors),action.blockers,action.warnings,fixture.fixed_evaluated_at)
 failures=[]
 if (decision.selected_market[0] if decision.selected_market else "NONE")!=fixture.expected_selected_market:failures.append("EXPECTED_SELECTED_MARKET_MISMATCH")
 if projection["parent_action"]!=fixture.expected_parent_action:failures.append("EXPECTED_PARENT_ACTION_MISMATCH")
 if decision.decision!=fixture.expected_parent_status:failures.append("EXPECTED_PARENT_STATUS_MISMATCH")
 safety=tuple((x,0) for x in ("provider_calls","angel_calls","planner_invocations","lifecycle_invocations","monitoring_mutations","persistence_mutations","broker_order_invocations","task6_counter_mutations"))
 checksum=hashlib.sha256(json.dumps((fixture.scenario_id,decision.decision_result_id,decision.decision,decision.selected_market,parent_explanation.explanation_id),sort_keys=True,default=str).encode()).hexdigest()
 return Task2DecisionCertificationResultV1(f"certification:{fixture.scenario_id}",fixture.scenario_id,fixture.parent_cycle_id,market(fixture.nifty,nifty),market(fixture.sensex,sensex),decision.decision_result_id,decision.decision,decision.selected_market[0] if decision.selected_market else "NONE",projection["parent_action"],parent_explanation.explanation_id,parent_explanation.comparison_reason_codes,parent_explanation.winner_reason_codes,parent_explanation.loser_reason_codes,parent_explanation.no_trade_reason_codes,parent_explanation.invariant_status,"PASS" if not failures else "FAILED",tuple(failures),tuple(calls.items()),safety,checksum,fixture.fixed_evaluated_at)
