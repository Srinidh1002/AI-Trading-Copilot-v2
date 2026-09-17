"""Market Phase Engine - Tracks NSE/BSE session states.
Handles entry cutoff, close drain, holiday awareness.
"""
from datetime import datetime, time, timedelta


# NSE holidays 2026 (extend as needed)
NSE_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-03-04",  # Holi
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-08-15",  # Independence Day
    "2026-09-14",  # Ganesh Chaturthi
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-21",  # Dussehra
    "2026-11-09",  # Diwali
    "2026-12-25",  # Christmas
}

BSE_HOLIDAYS_2026 = NSE_HOLIDAYS_2026  # Same for now


class MarketPhaseEngine:
    """Resolves market phase for NSE or BSE."""
    
    # Session times (IST)
    PRE_OPEN_START = time(9, 0)
    PRE_OPEN_END = time(9, 15)
    CONTINUOUS_START = time(9, 15)
    NEW_ENTRY_CUTOFF = time(15, 15)   # No new normal entries after this
    CLOSE_DRAIN_START = time(15, 15)  # NSE CAS window starts
    FINAL_EXIT = time(15, 28)          # Force close positions
    MARKET_CLOSE = time(15, 30)
    POST_CLOSE = time(16, 0)
    
    def __init__(self, market="NIFTY"):
        self.market = market.upper()
        self.holidays = NSE_HOLIDAYS_2026 if self.market == "NIFTY" else BSE_HOLIDAYS_2026
    
    def _is_holiday(self, dt=None):
        if dt is None:
            dt = datetime.now()
        return dt.strftime("%Y-%m-%d") in self.holidays
    
    def _is_weekend(self, dt=None):
        if dt is None:
            dt = datetime.now()
        return dt.weekday() >= 5  # 5=Sat, 6=Sun
    
    def get_phase(self, dt=None):
        """Returns (phase_name, can_enter, can_exit, note)."""
        if dt is None:
            dt = datetime.now()
        
        # Holiday or weekend
        if self._is_weekend(dt):
            return ("WEEKEND", False, False, "Market closed (weekend)")
        if self._is_holiday(dt):
            return ("HOLIDAY", False, False, "Market closed (holiday)")
        
        t = dt.time()
        
        if t < self.PRE_OPEN_START:
            return ("PRE_PREOPEN", False, False, "Before pre-open")
        elif t < self.PRE_OPEN_END:
            return ("PRE_OPEN", False, False, "Pre-open session")
        elif t < self.CONTINUOUS_START:
            return ("OPENING_TRANSITION", False, False, "Opening transition")
        elif t < self.NEW_ENTRY_CUTOFF:
            return ("CONTINUOUS", True, True, "Normal continuous session")
        elif t < self.FINAL_EXIT:
            return ("CLOSE_DRAIN", False, True, "Entry cutoff - exit only")
        elif t < self.MARKET_CLOSE:
            return ("CLOSING_AUCTION", False, True, "Closing auction")
        elif t < self.POST_CLOSE:
            return ("POST_CLOSE", False, True, "Post-close settlement")
        else:
            return ("CLOSED", False, False, "After hours")
    
    def can_enter(self, dt=None):
        phase, can_enter, _, _ = self.get_phase(dt)
        return can_enter
    
    def can_exit(self, dt=None):
        phase, _, can_exit, _ = self.get_phase(dt)
        return can_exit
    
    def is_market_open(self, dt=None):
        """True if continuous session active."""
        phase, _, _, _ = self.get_phase(dt)
        return phase in ("CONTINUOUS", "CLOSE_DRAIN", "CLOSING_AUCTION")
    
    def describe(self, dt=None):
        phase, ce, cx, note = self.get_phase(dt)
        return {
            "phase": phase,
            "can_enter": ce,
            "can_exit": cx,
            "note": note,
            "market": self.market,
        }


if __name__ == "__main__":
    for mkt in ["NIFTY", "SENSEX"]:
        eng = MarketPhaseEngine(mkt)
        print(f"\n{mkt}:")
        # Test various times today
        for test_time in [(9, 10), (9, 20), (10, 0), (14, 0), (15, 20), (15, 35), (15, 45), (16, 30)]:
            dt = datetime.now().replace(hour=test_time[0], minute=test_time[1], second=0)
            d = eng.describe(dt)
            print(f"  {test_time[0]:02d}:{test_time[1]:02d} -> {d['phase']:20s} enter={d['can_enter']} exit={d['can_exit']}")
