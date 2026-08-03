"""Provider-free Task 2C child/parent action projection."""
import json
from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1

def project_parent_pre_entry_action(*, parent_decision, nifty_action:PreEntryMarketActionV1, sensex_action:PreEntryMarketActionV1):
 if type(nifty_action) is not PreEntryMarketActionV1 or type(sensex_action) is not PreEntryMarketActionV1:raise TypeError("actions")
 selected=getattr(parent_decision,"selected_market",None)
 if selected is None:return {"parent_action":"NO_TRADE","selected_market":None,"reasons":tuple(getattr(parent_decision,"blockers",()) or ("NO_ACTIONABLE_MARKET",)),"invariant_status":"VALID"}
 action=nifty_action if selected==("NIFTY","NSE") else sensex_action if selected==("SENSEX","BSE") else None
 if action is None or action.action not in {"CALL","PUT"}:return {"parent_action":"UNAVAILABLE","selected_market":selected,"reasons":("SELECTED_MARKET_ACTION_INVARIANT_VIOLATION",),"invariant_status":"FAILED"}
 return {"parent_action":action.action,"selected_market":selected,"reasons":(f"SELECTED_{selected[0]}_{action.action}",),"invariant_status":"VALID"}

def build_task2_pre_entry_action_report(*, parent_decision, nifty_action:PreEntryMarketActionV1, sensex_action:PreEntryMarketActionV1):
 parent=project_parent_pre_entry_action(parent_decision=parent_decision,nifty_action=nifty_action,sensex_action=sensex_action)
 result={"schema_version":"task2_pre_entry_action_report.v1","parent":parent,"markets":[nifty_action.to_dict(),sensex_action.to_dict()],"action_resolver_evaluation_count":2,"planner_invocations":0,"lifecycle_invocations":0,"monitoring_mutations":0,"persistence_mutations":0,"broker_order_invocations":0}
 return json.loads(json.dumps(result,sort_keys=True,allow_nan=False))
