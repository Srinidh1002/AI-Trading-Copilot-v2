from dataclasses import FrozenInstanceError
from datetime import datetime,timezone
import pytest
from services.contracts import PaperTradeLifecycleStateV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(state='PLANNED',**kw): return PaperTradeLifecycleStateV1('state-1','plan-1','integrated-1','policy-1',state,NOW,**kw)
def terminal(state,**kw): return make(state,previous_state='OPEN',transition_sequence=1,terminal_reason='TEST',closed_at=NOW,terminal_target={'CLOSED_TARGET_1':'T1','CLOSED_TARGET_2':'T2','CLOSED_TARGET_3':'T3'}.get(state),is_terminal=True,**kw)
def test_valid_states_and_deterministic_serialization():
 assert make().transition_sequence==0
 assert make('WAITING_FOR_ENTRY',previous_state='PLANNED',transition_sequence=1).current_state=='WAITING_FOR_ENTRY'
 assert make('OPEN',previous_state='WAITING_FOR_ENTRY',transition_sequence=1).current_state=='OPEN'
 assert make('PARTIALLY_EXITED',previous_state='OPEN',transition_sequence=1).current_state=='PARTIALLY_EXITED'
 for state in ('CLOSED_TARGET_1','CLOSED_TARGET_2','CLOSED_TARGET_3','CLOSED_STOP','CLOSED_INVALIDATED','CLOSED_SESSION','CLOSED_EXPIRY'):assert terminal(state).is_terminal
 assert make('CANCELLED',previous_state='OPEN',transition_sequence=1,terminal_reason='X',cancelled_at=NOW,is_terminal=True).is_terminal
 assert make('BLOCKED',previous_state='OPEN',transition_sequence=1,terminal_reason='X',blocked_at=NOW,blockers=('X',),is_terminal=True).is_terminal
 assert make(metadata={'a':[1]}).to_json()==make(metadata={'a':[1]}).to_json()
@pytest.mark.parametrize('kwargs',[{'current_state':'BAD'},{'current_state':'OPEN','previous_state':'PLANNED','transition_sequence':1},{'current_state':'OPEN','transition_sequence':1},{'current_state':'CLOSED_STOP','previous_state':'OPEN','transition_sequence':1,'is_terminal':True},{'current_state':'BLOCKED','previous_state':'OPEN','transition_sequence':1,'terminal_reason':'x','blocked_at':NOW,'is_terminal':True},{'last_observation_id':'o'}])
def test_invalid_states_fail_closed(kwargs):
 if 'current_state' in kwargs:
  state=kwargs.pop('current_state');
  with pytest.raises((ValueError,TypeError)):make(state,**kwargs)
 else:
  with pytest.raises((ValueError,TypeError)):make(**kwargs)
def test_state_immutable_and_detached():
 s=make(metadata={'x':[1]});d=s.to_dict();d['metadata']['x'].append(2);assert s.to_dict()['metadata']=={'x':[1]}
 with pytest.raises(FrozenInstanceError):s.current_state='OPEN'
