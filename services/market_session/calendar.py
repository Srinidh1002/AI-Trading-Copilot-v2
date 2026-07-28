from dataclasses import dataclass
from datetime import date,time
from typing import Protocol
@dataclass(frozen=True,slots=True)
class TradingHoliday: exchange:str; trading_date:date; name:str; full_day:bool=True
@dataclass(frozen=True,slots=True)
class SpecialTradingSession:
    exchange:str; trading_date:date; name:str; pre_open_start:time|None; regular_open:time; regular_close:time; closing_end:time|None; analysis_allowed:bool; paper_preparation_allowed:bool; paper_execution_allowed:bool
class TradingCalendar(Protocol):
    def holiday_for(self,exchange:str,trading_date:date)->TradingHoliday|None: ...
    def special_session_for(self,exchange:str,trading_date:date)->SpecialTradingSession|None: ...
class EmptyTradingCalendar:
    trusted=False; source="EMPTY"
    def holiday_for(self,exchange,trading_date): return None
    def special_session_for(self,exchange,trading_date): return None
class InMemoryTradingCalendar:
    def __init__(self,holidays=(),special_sessions=(),*,trusted=False):
        self.trusted,self.source=trusted,"IN_MEMORY"; self._holidays={(h.exchange,h.trading_date):h for h in holidays}; self._special={(s.exchange,s.trading_date):s for s in special_sessions}
        if len(self._holidays)!=len(tuple(holidays)) or len(self._special)!=len(tuple(special_sessions)): raise ValueError("Duplicate calendar definitions.")
    def holiday_for(self,exchange,trading_date): return self._holidays.get((exchange,trading_date))
    def special_session_for(self,exchange,trading_date): return self._special.get((exchange,trading_date))
