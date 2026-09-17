"""Liquidity Gate - Reject illiquid / wide-spread options.
Prevents entry into untradeable contracts.
"""


class LiquidityGate:
    def __init__(self, max_spread_pct=2.0, min_volume=100, min_oi=500):
        self.max_spread_pct = max_spread_pct
        self.min_volume = min_volume
        self.min_oi = min_oi
    
    def check(self, option):
        """Return (pass: bool, reasons: list[str])."""
        reasons = []
        
        if not option:
            return False, ["NO_OPTION_DATA"]
        
        ltp = option.get("ltp", 0)
        bid = option.get("bid", 0)
        ask = option.get("ask", 0)
        vol = option.get("volume", 0)
        oi = option.get("oi", 0)
        spread_pct = option.get("spread_pct")
        
        # LTP must be positive
        if ltp <= 0:
            reasons.append("INVALID_LTP")
        
        # Bid/ask must exist
        if bid <= 0 or ask <= 0:
            reasons.append("NO_BID_ASK")
        elif bid >= ask:
            reasons.append("INVERTED_SPREAD")
        
        # Spread check
        if spread_pct is not None and spread_pct > self.max_spread_pct:
            reasons.append(f"WIDE_SPREAD({spread_pct:.2f}%)")
        
        # Volume
        if vol < self.min_volume:
            reasons.append(f"LOW_VOLUME({vol})")
        
        # OI
        if oi < self.min_oi:
            reasons.append(f"LOW_OI({oi})")
        
        return len(reasons) == 0, reasons
    
    def describe(self):
        return f"LiquidityGate(max_spread={self.max_spread_pct}% min_vol={self.min_volume} min_oi={self.min_oi})"


if __name__ == "__main__":
    gate = LiquidityGate()
    
    # Test: good option
    good = {"ltp": 175, "bid": 174.5, "ask": 175.5, "spread_pct": 0.57,
            "volume": 5000, "oi": 20000}
    ok, reasons = gate.check(good)
    print(f"Good: pass={ok} reasons={reasons}")
    
    # Test: wide spread
    wide = {"ltp": 175, "bid": 168, "ask": 176, "spread_pct": 4.57,
            "volume": 5000, "oi": 20000}
    ok, reasons = gate.check(wide)
    print(f"Wide: pass={ok} reasons={reasons}")
    
    # Test: low liquidity
    illiq = {"ltp": 50, "bid": 49, "ask": 51, "spread_pct": 4.0,
             "volume": 5, "oi": 20}
    ok, reasons = gate.check(illiq)
    print(f"Illiquid: pass={ok} reasons={reasons}")
    
    # Test: inverted spread
    inv = {"ltp": 175, "bid": 176, "ask": 174, "spread_pct": None,
           "volume": 5000, "oi": 20000}
    ok, reasons = gate.check(inv)
    print(f"Inverted: pass={ok} reasons={reasons}")
