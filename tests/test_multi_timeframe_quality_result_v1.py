from datetime import datetime,timezone
import pytest
from services.contracts import MultiTimeframeQualityResultV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
@pytest.mark.parametrize("n",range(50))
def test_result(n):assert MultiTimeframeQualityResultV1("q",NOW,"s","READY","NIFTY","NSE",("5m",),("5m",),(),(),(),(),(),(),1,1,NOW,0).quality_status=="READY"
