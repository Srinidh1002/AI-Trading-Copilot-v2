from datetime import date
from services.market_session import InMemoryTradingCalendar,TradingHoliday
def test_in_memory_calendar_is_exchange_scoped():
    calendar=InMemoryTradingCalendar((TradingHoliday("NSE",date(2026,7,27),"Test"),),trusted=True)
    assert calendar.holiday_for("NSE",date(2026,7,27)).name == "Test" and calendar.holiday_for("BSE",date(2026,7,27)) is None
