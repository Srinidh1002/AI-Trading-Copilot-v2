"""Certification-only deterministic explanation report."""
import hashlib,json
def build_task2_decision_explanation_report(*,parent_explanation,nifty_explanation,sensex_explanation):
 data={"schema_version":"task2_decision_explanation_report.v1","parent":parent_explanation.to_dict(),"markets":[nifty_explanation.to_dict(),sensex_explanation.to_dict()],"child_explanation_build_count":2,"parent_explanation_build_count":1,"planner_invocations":0,"lifecycle_invocations":0,"monitoring_mutations":0,"persistence_mutations":0,"broker_order_invocations":0}
 raw=json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False);data["checksum"]=hashlib.sha256(raw.encode()).hexdigest();return data
