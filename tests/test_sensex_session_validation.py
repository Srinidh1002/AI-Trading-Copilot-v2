from datetime import datetime
from zoneinfo import ZoneInfo
from services.market_session import validate_session_timestamp
def test_sensex_regular_and_weekend():
    zone=ZoneInfo("Asia/Kolkata"); regular=datetime(2026,7,27,10,tzinfo=zone); weekend=datetime(2026,7,26,10,tzinfo=zone)
    assert validate_session_timestamp(symbol="SENSEX",exchange="BSE",market_timestamp=regular,evaluated_at=regular).analysis_allowed
    assert not validate_session_timestamp(symbol="SENSEX",exchange="BSE",market_timestamp=weekend,evaluated_at=weekend).analysis_allowed
