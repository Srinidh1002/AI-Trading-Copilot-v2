import pytest
from services.contracts import CANONICAL_PAPER_TRADE_LIFECYCLE_STATES,is_legal_paper_trade_lifecycle_transition
LEGAL={'PLANNED':{'WAITING_FOR_ENTRY','CANCELLED','BLOCKED'},'WAITING_FOR_ENTRY':{'OPEN','CANCELLED','CLOSED_INVALIDATED','CLOSED_SESSION','CLOSED_EXPIRY','BLOCKED'},'OPEN':{'PARTIALLY_EXITED','CLOSED_TARGET_1','CLOSED_TARGET_2','CLOSED_TARGET_3','CLOSED_STOP','CLOSED_INVALIDATED','CLOSED_SESSION','CLOSED_EXPIRY','CANCELLED','BLOCKED'},'PARTIALLY_EXITED':{'PARTIALLY_EXITED','CLOSED_TARGET_2','CLOSED_TARGET_3','CLOSED_STOP','CLOSED_INVALIDATED','CLOSED_SESSION','CLOSED_EXPIRY','CANCELLED','BLOCKED'}}
@pytest.mark.parametrize('previous,next_state',[(a,b) for a in sorted(CANONICAL_PAPER_TRADE_LIFECYCLE_STATES) for b in sorted(CANONICAL_PAPER_TRADE_LIFECYCLE_STATES)])
def test_every_canonical_pair(previous,next_state):assert is_legal_paper_trade_lifecycle_transition(previous,next_state)==(next_state in LEGAL.get(previous,set()))
@pytest.mark.parametrize('previous,next_state',[('BAD','OPEN'),('OPEN','BAD')])
def test_invalid_names_rejected(previous,next_state):
 with pytest.raises(ValueError):is_legal_paper_trade_lifecycle_transition(previous,next_state)
