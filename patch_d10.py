"""D10 - total_pnl and win/loss tally use net P&L, not gross.

Before: self.total_pnl += pnl (gross)
        winning_trades counted on gross > 0
After:  both use trade['net_pnl'] when available, falling back to gross
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D10_net_pnl" in src:
    print("D10 already applied")
    raise SystemExit(0)

old = """        self.total_pnl += pnl
        
        if pnl > 0:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0"""
new = """        # D10_net_pnl - running total uses net P&L when available
        _pnl_for_total = trade.get('net_pnl')
        if _pnl_for_total is None:
            _pnl_for_total = pnl
        self.total_pnl += _pnl_for_total
        
        if _pnl_for_total > 0:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0"""
if old not in src:
    raise SystemExit("D10 anchor not found")
src = src.replace(old, new, 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D10: total_pnl and win/loss tally use net P&L")
