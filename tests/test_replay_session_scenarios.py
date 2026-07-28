from datetime import datetime
from zoneinfo import ZoneInfo
from services.market_session import InMemoryTradingCalendar,TradingHoliday,validate_session_timestamp
def test_synthetic_holiday_and_future_scenarios_are_deterministic():
    zone=ZoneInfo("Asia/Kolkata"); day=datetime(2026,7,27,10,tzinfo=zone); calendar=InMemoryTradingCalendar((TradingHoliday("NSE",day.date(),"Synthetic holiday"),),trusted=True)
    holiday=validate_session_timestamp(symbol="NIFTY",exchange="NSE",market_timestamp=day,evaluated_at=day,calendar=calendar,id_factory=lambda:"one")
    future=validate_session_timestamp(symbol="SENSEX",exchange="BSE",market_timestamp=day.replace(minute=10),evaluated_at=day,id_factory=lambda:"two")
    assert holiday.session_state == "HOLIDAY" and future.future_timestamp
