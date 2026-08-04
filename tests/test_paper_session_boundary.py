from datetime import datetime
from zoneinfo import ZoneInfo
from services.market_session import validate_session_timestamp
def test_pre_open_strict_session_blocks_execution_eligibility():
    zone=ZoneInfo("Asia/Kolkata"); moment=datetime(2026,7,27,9,0,tzinfo=zone); result=validate_session_timestamp(symbol="NIFTY",exchange="NSE",market_timestamp=moment,evaluated_at=moment,validation_mode="STRICT_EXECUTION")
    assert result.paper_execution_allowed is False
