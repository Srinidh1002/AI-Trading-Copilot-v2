from datetime import datetime,timezone
import pytest
from services.contracts import TimeframeEvidenceV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
@pytest.mark.parametrize("n",range(55))
def test_evidence(n):assert TimeframeEvidenceV1("e",NOW,"NIFTY","NSE","5m","s","q","VALID",60,60,0,NOW,NOW,NOW,NOW,0,600,60,True,True).history_sufficient
