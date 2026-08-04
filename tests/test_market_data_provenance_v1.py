from datetime import datetime,timezone
import pytest
from services.contracts import MarketDataProvenanceV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
@pytest.mark.parametrize("n",range(40))
def test_provenance(n):assert MarketDataProvenanceV1("TEST",None,None,"TEST",NOW,NOW,False,None,None).provider=="TEST"
