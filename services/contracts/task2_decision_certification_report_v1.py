"""Immutable aggregate Task 2 decision-certification output."""
from dataclasses import asdict,dataclass
from datetime import datetime
import hashlib,json
from services.contracts.task2_decision_certification_result_v1 import Task2DecisionCertificationResultV1
@dataclass(frozen=True,slots=True)
class Task2DecisionCertificationAggregateV1:
 certification_run_id:str;task_id:str;started_at:datetime;completed_at:datetime;policy_versions:tuple[tuple[str,str],...];total_scenarios:int;passed_scenarios:int;failed_scenarios:int;overall_status:str;scenario_results:tuple[Task2DecisionCertificationResultV1,...];coverage_summary:tuple[tuple[str,int],...];aggregate_call_counts:tuple[tuple[str,int],...];aggregate_safety_counters:tuple[tuple[str,int],...];coverage_failure_codes:tuple[str,...];deterministic_checksum:str;execution_mode:str="PAPER";live_execution_eligible:bool=False;schema_version:str="task2_decision_certification_aggregate.v1"
 def __post_init__(self):
  if self.task_id!="TASK_2" or self.execution_mode!="PAPER" or self.live_execution_eligible is not False or self.overall_status not in {"PASS","FAILED"}:raise ValueError("aggregate safety")
  if self.total_scenarios!=len(self.scenario_results) or self.passed_scenarios+self.failed_scenarios!=self.total_scenarios:raise ValueError("aggregate counts")
 def to_json(self):return json.dumps(asdict(self),default=str,sort_keys=True,separators=(",",":"))
 def semantic_checksum(self):return hashlib.sha256(self.to_json().encode()).hexdigest()
