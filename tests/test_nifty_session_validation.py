from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from services.market_session import validate_session_timestamp
IST=ZoneInfo("Asia/Kolkata")
@pytest.mark.parametrize("hour,minute,state",[(8,59,"CLOSED"),(9,0,"PRE_OPEN"),(9,10,"PRE_OPEN"),(9,14,"PRE_OPEN"),(9,15,"REGULAR"),(10,0,"REGULAR"),(15,31,"POST_CLOSE")])
def test_nifty_boundaries(hour,minute,state):
    value=datetime(2026,7,27,hour,minute,tzinfo=IST); assert validate_session_timestamp(symbol="NIFTY",exchange="NSE",market_timestamp=value,evaluated_at=value).session_state == state
