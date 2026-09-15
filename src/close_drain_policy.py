"""Close Drain Policy - Config-driven entry cutoff and forced exit windows.
"""


class CloseDrainPolicy:
    def __init__(self, market="NIFTY"):
        self.market = market.upper()
        
        # Time windows (IST)
        if self.market == "NIFTY":
            self.new_entry_cutoff = (15, 10)   # No new entries after 15:10
            self.close_drain_start = (15, 15)  # Start draining positions
            self.final_exit = (15, 25)         # Force close all by 15:25
        else:  # SENSEX
            self.new_entry_cutoff = (15, 5)
            self.close_drain_start = (15, 10)
            self.final_exit = (15, 20)
    
    def can_enter_new(self, dt=None):
        from datetime import datetime
        if dt is None:
            dt = datetime.now()
        t = (dt.hour, dt.minute)
        return t < self.new_entry_cutoff
    
    def in_close_drain(self, dt=None):
        from datetime import datetime
        if dt is None:
            dt = datetime.now()
        t = (dt.hour, dt.minute)
        return self.close_drain_start <= t < self.final_exit
    
    def must_force_exit(self, dt=None):
        from datetime import datetime
        if dt is None:
            dt = datetime.now()
        t = (dt.hour, dt.minute)
        return t >= self.final_exit
    
    def describe(self, dt=None):
        return {
            "market": self.market,
            "new_entry_cutoff": f"{self.new_entry_cutoff[0]:02d}:{self.new_entry_cutoff[1]:02d}",
            "close_drain_start": f"{self.close_drain_start[0]:02d}:{self.close_drain_start[1]:02d}",
            "final_exit": f"{self.final_exit[0]:02d}:{self.final_exit[1]:02d}",
            "can_enter": self.can_enter_new(dt),
            "in_close_drain": self.in_close_drain(dt),
            "must_force_exit": self.must_force_exit(dt),
        }


if __name__ == "__main__":
    from datetime import datetime
    
    for market in ["NIFTY", "SENSEX"]:
        p = CloseDrainPolicy(market)
        print(f"\n{market}:")
        for h, m in [(14, 0), (15, 0), (15, 8), (15, 12), (15, 18), (15, 30)]:
            dt = datetime.now().replace(hour=h, minute=m, second=0)
            d = p.describe(dt)
            print(f"  {h:02d}:{m:02d} -> enter={d['can_enter']} drain={d['in_close_drain']} force={d['must_force_exit']}")
