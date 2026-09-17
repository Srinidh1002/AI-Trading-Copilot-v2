"""Single-result safe serializer for Task 2E2 certification."""
from dataclasses import asdict
import json
from services.contracts.task2_decision_certification_result_v1 import Task2DecisionCertificationResultV1
def render_task2_decision_certification_report(result:Task2DecisionCertificationResultV1)->str:
 if type(result) is not Task2DecisionCertificationResultV1:raise TypeError("result")
 return json.dumps(asdict(result),default=str,sort_keys=True,separators=(",",":"))
