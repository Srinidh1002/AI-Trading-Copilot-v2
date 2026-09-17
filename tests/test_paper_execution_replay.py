from datetime import datetime,timezone
from dataclasses import replace
import pytest
from services.contracts import CanonicalPaperExecutionResultV1,PaperExecutionObservationV1
from services.paper import replay_canonical_paper_execution
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
def canonical(**c):
 v=dict(canonical_execution_result_id="c",created_at=NOW,pipeline_status="EXECUTED",execution_request_id="r",authorization_id="a",execution_result_id="e",idempotency_key="k",underlying_symbol="NIFTY",exchange="NSE",action="BUY",option_type="CALL",position_side="LONG",trading_symbol="NIFTYCE",quantity=50,lots=1,execution_status="FILLED",reference_price=10.,fill_price=10.,capital_used=500.,realized_maximum_loss=100.,submitted_at=NOW,filled_at=NOW);v.update(c);return CanonicalPaperExecutionResultV1(**v)
def observations(c):
 return (PaperExecutionObservationV1("execution",NOW,"EXECUTION","EXECUTED",canonical_execution_result_id=c.canonical_execution_result_id,execution_request_id=c.execution_request_id,authorization_id=c.authorization_id,execution_result_id=c.execution_result_id,idempotency_key=c.idempotency_key,underlying_symbol=c.underlying_symbol,exchange=c.exchange,action=c.action,option_type=c.option_type,position_side=c.position_side,trading_symbol=c.trading_symbol,quantity=c.quantity,lots=c.lots,fill_price=c.fill_price,filled_at=NOW),PaperExecutionObservationV1("pipeline",NOW,"PIPELINE_RESULT","EXECUTED",canonical_execution_result_id=c.canonical_execution_result_id,execution_request_id=c.execution_request_id,authorization_id=c.authorization_id,execution_result_id=c.execution_result_id,idempotency_key=c.idempotency_key,underlying_symbol=c.underlying_symbol,exchange=c.exchange,action=c.action,option_type=c.option_type,position_side=c.position_side,trading_symbol=c.trading_symbol,quantity=c.quantity,lots=c.lots,fill_price=c.fill_price,filled_at=NOW))
@pytest.mark.parametrize("repeat",range(90))
def test_replay_matches_recorded_execution_without_execution(repeat):
 c=canonical();r=replay_canonical_paper_execution(canonical_execution_result=c,observations=observations(c),clock=lambda:NOW,replay_result_id_factory=lambda:f"r{repeat}");assert r.replay_status=="MATCHED"
def test_replay_reports_identity_mismatch_and_incomplete():
 c=canonical();bad=list(observations(c));bad[-1]=replace(bad[-1],underlying_symbol="SENSEX",exchange="BSE")
 assert replay_canonical_paper_execution(canonical_execution_result=c,observations=bad,clock=lambda:NOW).replay_status=="MISMATCHED"
 assert replay_canonical_paper_execution(canonical_execution_result=c,observations=(),clock=lambda:NOW).replay_status=="INCOMPLETE"
