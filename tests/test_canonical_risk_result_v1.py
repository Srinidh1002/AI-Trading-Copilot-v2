from __future__ import annotations
import json
from dataclasses import replace
from datetime import date,datetime,timezone,timedelta
import pytest
from services.contracts.final_decision_v1 import FinalDecisionV1,DataHealthSummary,RiskSummary
from services.contracts.trade_plan_v1 import TradePlanV1
from services.contracts.position_size_result_v1 import PositionSizeResultV1
from services.contracts.canonical_risk_result_v1 import CanonicalRiskResultV1

NOW=datetime(2026,7,27,10,tzinfo=timezone.utc)
def decision(action="BUY"):
 return FinalDecisionV1(snapshot_id="s",decision_id="d",symbol="NIFTY",exchange="NSE",instrument_type="OPTION",created_at=NOW,market_timestamp=NOW,action=action,authorization_status="ANALYSIS_ONLY",execution_status="NOT_REQUESTED",risk=RiskSummary(risk_status="APPROVED"),data_health=DataHealthSummary(overall_status="VALID",validation_passed=True))
def plan():
 return TradePlanV1("p",NOW,"s","a","d","sel","con","NIFTY","NSE","BUY","CALL","SYM",date(2026,7,30),25000,50,100,"LAST",90,120,"X","X",NOW,NOW+timedelta(minutes=5),"READY_FOR_RISK",True)
def sizing(status="APPROVED"):
 approved=status=="APPROVED"; return PositionSizeResultV1("z",NOW,"s","a","d","sel","p","con","NIFTY","NSE","BUY","CALL","SYM",date(2026,7,30),25000,50,100 if approved else None,90 if approved else None,120 if approved else None,100000 if approved else None,10000 if approved else None,2000 if approved else None,10 if approved else None,500 if approved else None,2 if approved else None,2 if approved else None,100 if approved else None,10000 if approved else None,1000 if approved else None,2000 if approved else None,2 if approved else None,status,approved,approved,False,blockers=() if approved else ("blocked",))
def make(**changes):
 values=dict(result_id="r",created_at=NOW,snapshot_id="s",analysis_id="a",decision_id="d",trade_plan_result_id="tp",sizing_result_id="z",decision=decision(),trade_plan=plan(),sizing_result=sizing(),risk_status="RISK_APPROVED")
 values.update(changes); return CanonicalRiskResultV1(**values)
def test_approved_result_is_frozen_slotted_and_valid():
 value=make(); assert value.risk_status=="RISK_APPROVED" and not hasattr(value,"__dict__")
 with pytest.raises(Exception): value.result_id="x"
@pytest.mark.parametrize("field,value",[("schema_version","bad"),("created_at",datetime(2026,7,27)),("result_id",""),("snapshot_id",""),("decision_id",""),("risk_status","BAD"),("trade_plan",None),("sizing_result",None),("sizing_result_id",None),("blockers",("x",))])
def test_invalid_approved_contract_states_reject(field,value):
 with pytest.raises(ValueError): make(**{field:value})
@pytest.mark.parametrize("status,sizing_status",[("INSUFFICIENT_CAPITAL","INSUFFICIENT_CAPITAL"),("INVALID_RISK","INVALID_RISK"),("LIMIT_EXCEEDED","LIMIT_EXCEEDED"),("BLOCKED","BLOCKED"),("FAILED","FAILED")])
def test_nonapproved_statuses_require_honest_blockers(status,sizing_status):
 value=make(risk_status=status,sizing_result=sizing(sizing_status),blockers=("blocked",)); assert value.risk_status==status
@pytest.mark.parametrize("field,value",[("snapshot_id","other"),("analysis_id","other"),("decision_id","other")])
def test_identity_mismatches_reject(field,value):
 with pytest.raises(ValueError): make(**{field:value})
def test_no_action_requires_nonactionable_decision_and_no_plan():
 value=CanonicalRiskResultV1("r",NOW,"s","a","d",None,None,decision("WAIT"),None,None,"NO_ACTION"); assert value.risk_status=="NO_ACTION"
def test_metadata_copy_serialization_and_semantics_are_deterministic():
 metadata={"a":1}; value=make(metadata=metadata); metadata["a"]=2
 assert value.metadata=={"a":1} and json.loads(value.to_json())["result_id"]=="r" and "result_id" not in value.semantic_dict() and "created_at" not in value.semantic_dict()
@pytest.mark.parametrize("metadata",[{"x":float("nan")},{"x":float("inf")},{"x":object()}])
def test_unsafe_metadata_rejects(metadata):
 with pytest.raises(ValueError): make(metadata=metadata)

@pytest.mark.parametrize("warning",["stale","future","missing-entry","missing-stop","missing-target","capital","risk","limit","session","identity"])
def test_warnings_are_preserved_deterministically(warning):
 value=make(warnings=(warning,)); assert value.to_dict()["warnings"]==[warning]

@pytest.mark.parametrize("result_id",["r-1","r-2","r-3","r-4","r-5","r-6"])
def test_generated_identity_is_excluded_from_semantic_output(result_id):
 assert "result_id" not in make(result_id=result_id).semantic_dict()
