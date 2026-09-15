"""Multi-Exit Engine - Underlying + technical + premium + time + regime exits.
Also tracks MFE (max favorable excursion) and MAE (max adverse excursion).
"""
from datetime import datetime, timedelta


class ExitEngine:
    def __init__(self,
                 premium_stop_pct=-5.0,
                 time_stop_minutes=90,
                 underlying_invalidation_pct=0.5):
        self.premium_stop_pct = premium_stop_pct
        self.time_stop_minutes = time_stop_minutes
        self.underlying_invalidation_pct = underlying_invalidation_pct
    
    def evaluate(self, trade_state):
        """trade_state keys:
            entry_price, entry_spot, current_price, current_spot,
            direction (CE/PE), signal (BUY), entry_time,
            max_favorable, max_adverse,
            tech_invalidated (bool), regime_flipped (bool),
            event_active (bool)
        Returns (action, reason, details)
        action in ("HOLD", "EXIT")
        """
        entry_price = trade_state.get("entry_price", 0)
        current_price = trade_state.get("current_price", 0)
        entry_spot = trade_state.get("entry_spot", 0)
        current_spot = trade_state.get("current_spot", 0)
        direction = trade_state.get("direction", "CE")
        entry_time = trade_state.get("entry_time")
        
        if entry_price <= 0 or current_price <= 0:
            return ("HOLD", "INSUFFICIENT_DATA", {})
        
        # P&L calc
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        
        # 1. Premium emergency stop
        if pnl_pct <= self.premium_stop_pct:
            return ("EXIT", "PREMIUM_EMERGENCY_STOP", {"pnl_pct": pnl_pct})
        
        # 2. Underlying invalidation
        if entry_spot > 0 and current_spot > 0:
            spot_move = ((current_spot - entry_spot) / entry_spot) * 100
            if direction == "CE" and spot_move < -self.underlying_invalidation_pct:
                return ("EXIT", "UNDERLYING_INVALIDATED", {"spot_move_pct": spot_move})
            if direction == "PE" and spot_move > self.underlying_invalidation_pct:
                return ("EXIT", "UNDERLYING_INVALIDATED", {"spot_move_pct": spot_move})
        
        # 3. Technical invalidation
        if trade_state.get("tech_invalidated"):
            return ("EXIT", "TECHNICAL_INVALIDATED", {})
        
        # 4. Regime flip
        if trade_state.get("regime_flipped"):
            return ("EXIT", "REGIME_FLIPPED", {})
        
        # 5. Event risk exit
        if trade_state.get("event_active"):
            return ("EXIT", "EVENT_RISK_ACTIVE", {})
        
        # 6. Time stop (timezone-safe, allows injected current_time)
        if entry_time:
            try:
                now = trade_state.get("current_time") or datetime.now()
                et = entry_time
                if et.tzinfo is not None and now.tzinfo is None:
                    now = now.replace(tzinfo=et.tzinfo)
                elif et.tzinfo is None and now.tzinfo is not None:
                    et = et.replace(tzinfo=now.tzinfo)
                elapsed_min = (now - et).total_seconds() / 60
                if elapsed_min >= self.time_stop_minutes:
                    return ("EXIT", "TIME_STOP", {"elapsed_minutes": round(elapsed_min, 1)})
            except Exception:
                pass
        
        return ("HOLD", "ACTIVE", {"pnl_pct": pnl_pct})


class MFE_MAE_Tracker:
    """Tracks maximum favorable and adverse excursions per trade."""
    def __init__(self):
        self.trades = {}  # trade_id -> {max_favorable, max_adverse, entry_price}
    
    def register(self, trade_id, entry_price):
        self.trades[trade_id] = {
            "entry_price": entry_price,
            "max_favorable": 0.0,
            "max_adverse": 0.0,
            "peak_pnl_pct": 0.0,
            "trough_pnl_pct": 0.0,
            "ticks": 0,
        }
    
    def update(self, trade_id, current_price):
        if trade_id not in self.trades:
            return
        t = self.trades[trade_id]
        entry = t["entry_price"]
        pnl = current_price - entry
        pnl_pct = (pnl / entry * 100) if entry > 0 else 0
        
        if pnl_pct > t["peak_pnl_pct"]:
            t["peak_pnl_pct"] = pnl_pct
        if pnl_pct < t["trough_pnl_pct"]:
            t["trough_pnl_pct"] = pnl_pct
        
        t["max_favorable"] = max(t["max_favorable"], pnl)
        t["max_adverse"] = min(t["max_adverse"], pnl)
        t["ticks"] += 1
    
    def snapshot(self, trade_id):
        if trade_id not in self.trades:
            return {}
        return dict(self.trades[trade_id])


if __name__ == "__main__":
    # Test ExitEngine
    ee = ExitEngine()
    
    # Test 1: Holding
    t1 = {
        "entry_price": 175, "current_price": 180,
        "entry_spot": 23600, "current_spot": 23610,
        "direction": "CE", "entry_time": datetime.now(),
    }
    print("Test 1 (holding):", ee.evaluate(t1))
    
    # Test 2: Premium stop
    t2 = dict(t1)
    t2["current_price"] = 165
    print("Test 2 (premium stop):", ee.evaluate(t2))
    
    # Test 3: Underlying invalidation
    t3 = dict(t1)
    t3["entry_spot"] = 23600
    t3["current_spot"] = 23480  # -0.5% for CE
    print("Test 3 (underlying invalidation):", ee.evaluate(t3))
    
    # Test MFE/MAE
    tracker = MFE_MAE_Tracker()
    tracker.register("T1", 175)
    for p in [176, 178, 172, 180, 170, 185]:
        tracker.update("T1", p)
    print()
    print("MFE/MAE snapshot:", tracker.snapshot("T1"))
