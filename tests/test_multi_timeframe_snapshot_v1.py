from datetime import datetime,timezone
import pytest
from services.contracts import TimeframeEvidenceV1,MultiTimeframeSnapshotV1
NOW=datetime(2025,1,1,tzinfo=timezone.utc)
def e(tf):return TimeframeEvidenceV1(tf,NOW,"NIFTY","NSE",tf,"s","q","VALID",60,60,0,NOW,NOW,NOW,NOW,0,600,1,True,True)
@pytest.mark.parametrize("n",range(55))
def test_snapshot(n):assert MultiTimeframeSnapshotV1("s",NOW,"NIFTY","NSE",("5m",),(e("5m"),),"5m",NOW).anchor_timeframe=="5m"
