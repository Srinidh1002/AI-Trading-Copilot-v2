from datetime import datetime
from zoneinfo import ZoneInfo
from services.market_session import validate_session_timestamp
def test_regular_session_is_deterministic():
    now=datetime(2026,7,27,10,0,tzinfo=ZoneInfo("Asia/Kolkata")); result=validate_session_timestamp(symbol="NIFTY",exchange="NSE",market_timestamp=now,evaluated_at=now,id_factory=lambda:"validation")
    assert result.session_state == "REGULAR" and result.semantic_dict() == result.semantic_dict()
