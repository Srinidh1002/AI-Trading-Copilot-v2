"""Explicit ownership boundary: the entry brain cannot exit an entered PAPER position."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class PostEntryAuthorityPolicyV1:
 entry_brain_may_mutate_position:bool=False
 position_monitor_owner:str="POSITION_MONITOR"
 exit_authority:str="PAPER_LIFECYCLE_EVALUATOR"
 contextual_changes_informational_only:bool=True
 execution_mode:str="PAPER"
 def __post_init__(self):
  if self.entry_brain_may_mutate_position or self.position_monitor_owner!="POSITION_MONITOR" or self.exit_authority!="PAPER_LIFECYCLE_EVALUATOR" or self.execution_mode!="PAPER": raise ValueError("canonical post-entry ownership violated")
