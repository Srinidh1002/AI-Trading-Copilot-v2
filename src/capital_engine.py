"""Capital Engine - Deployable capital, lot sizing, and paper fill model.
Includes realistic bid/ask fills + transaction costs.
"""


class CapitalEngine:
    # D6_tick_align - options trade on a 0.05 grid on NSE/BSE F&O
    OPTION_TICK = 0.05

    def __init__(self, deployable_capital=100000,
                 brokerage_per_order=20,
                 stt_pct=0.0625,      # 0.0625% on sell side only
                 exchange_txn_pct=0.05,  # ~0.05% of premium
                 gst_pct=18,
                 sebi_pct=0.0001,
                 stamp_duty_pct=0.003,
                 slippage_pct=0.15):
        self.capital = deployable_capital
        self.brokerage = brokerage_per_order
        self.stt_pct = stt_pct
        self.exchange_pct = exchange_txn_pct
        self.gst_pct = gst_pct
        self.sebi_pct = sebi_pct
        self.stamp_pct = stamp_duty_pct
        self.slippage_pct = slippage_pct

    @staticmethod
    def _round_to_tick(price, tick=None):
        """D6_tick_align - round to nearest valid tick (0.05 default)."""
        if price is None:
            return None
        t = tick if tick is not None else CapitalEngine.OPTION_TICK
        if t <= 0:
            return round(price, 2)
        return round(round(price / t) * t, 2)

    def compute_lot_size(self, premium, lot_size):
        """How many lots fit within capital?"""
        if premium <= 0 or lot_size <= 0:
            return 0
        cost_per_lot = premium * lot_size
        return int(self.capital // cost_per_lot)
    
    def compute_paper_fill(self, bid, ask, ltp, direction="BUY"):
        """Simulate realistic fill for paper trade.
        Returns (fill_price, status).
        STRICT: requires valid bid/ask, no LTP fallback.
        """
        if direction == "BUY":
            if not ask or ask <= 0:
                return (None, "NO_VALID_ASK")
            base = ask
        else:
            if not bid or bid <= 0:
                return (None, "NO_VALID_BID")
            base = bid
        
        # Sanity check: bid must be < ask in normal book
        if bid > 0 and ask > 0 and bid >= ask:
            return (None, "INVERTED_SPREAD")
        
        slippage = base * (self.slippage_pct / 100)
        fill = base + slippage if direction == "BUY" else base - slippage
        # D6_tick_align - round to 0.05 grid
        return (self._round_to_tick(fill), "OK")
    
    def compute_costs(self, entry_price, exit_price, quantity, side="BUY"):
        """Estimate total transaction costs for one round-trip trade."""
        buy_value = entry_price * quantity
        sell_value = exit_price * quantity
        
        # Brokerage (per order)
        brokerage = self.brokerage * 2  # entry + exit
        
        # STT: only on sell side for options
        stt = sell_value * (self.stt_pct / 100)
        
        # Exchange transaction charge
        exchange = (buy_value + sell_value) * (self.exchange_pct / 100)
        
        # SEBI charges
        sebi = (buy_value + sell_value) * (self.sebi_pct / 100)
        
        # Stamp duty (on buy side)
        stamp = buy_value * (self.stamp_pct / 100)
        
        # GST (on brokerage + exchange + sebi)
        gst = (brokerage + exchange + sebi) * (self.gst_pct / 100)
        
        total = brokerage + stt + exchange + sebi + stamp + gst
        
        return {
            "brokerage": round(brokerage, 2),
            "stt": round(stt, 2),
            "exchange": round(exchange, 2),
            "sebi": round(sebi, 2),
            "stamp": round(stamp, 2),
            "gst": round(gst, 2),
            "total": round(total, 2),
        }
    
    def compute_net_pnl(self, entry_price, exit_price, quantity, direction):
        """Net P&L after costs."""
        if direction == "BUY":
            gross = (exit_price - entry_price) * quantity
        else:
            gross = (entry_price - exit_price) * quantity
        
        costs = self.compute_costs(entry_price, exit_price, quantity, "SELL")
        net = gross - costs["total"]
        
        return {
            "gross_pnl": round(gross, 2),
            "costs": costs,
            "net_pnl": round(net, 2),
            "net_pnl_pct": round((net / (entry_price * quantity)) * 100, 3),
        }


if __name__ == "__main__":
    eng = CapitalEngine(deployable_capital=100000)
    
    # Test 1: lot sizing
    lots = eng.compute_lot_size(premium=175, lot_size=65)
    print(f"Lots affordable (175x65 from 100k): {lots}")
    
    lots2 = eng.compute_lot_size(premium=500, lot_size=20)
    print(f"Lots affordable SENSEX (500x20): {lots2}")
    
    # Test 2: paper fill
    entry = eng.compute_paper_fill(bid=174, ask=175, ltp=174.5, direction="BUY")
    exit_p = eng.compute_paper_fill(bid=200, ask=201, ltp=200.5, direction="SELL")
    print(f"Entry fill: {entry} (from bid=174 ask=175)")
    print(f"Exit fill: {exit_p} (from bid=200 ask=201)")
    
    # Test 3: costs
    print()
    pnl = eng.compute_net_pnl(entry, exit_p, quantity=65, direction="BUY")
    print(f"Gross: ₹{pnl['gross_pnl']}")
    print(f"Costs: ₹{pnl['costs']['total']}")
    print(f"Net:   ₹{pnl['net_pnl']} ({pnl['net_pnl_pct']}%)")
    print(f"Cost breakdown:")
    for k, v in pnl['costs'].items():
        if k != 'total':
            print(f"  {k}: ₹{v}")
