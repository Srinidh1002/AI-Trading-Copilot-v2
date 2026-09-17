from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class MarketDecisionExplanationPolicyV1:
 policy_id:str="market-decision-explanation";policy_version:str="market_decision_explanation_policy.v1";max_summary_entries:int=3;execution_mode:str="PAPER";live_execution_eligible:bool=False
 def __post_init__(self):
  if self.policy_id!="market-decision-explanation" or self.policy_version!="market_decision_explanation_policy.v1" or self.max_summary_entries!=3 or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("policy")
