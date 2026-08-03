from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class PreEntryActionPolicyV1:
 policy_id:str="pre-entry-action-policy";policy_version:str="pre_entry_action_policy.v1";execution_mode:str="PAPER";live_execution_eligible:bool=False
 def __post_init__(self):
  if self.policy_id!="pre-entry-action-policy" or self.policy_version!="pre_entry_action_policy.v1" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False:raise ValueError("PAPER policy")
