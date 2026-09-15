"""R10 focused tests - session_history uses reconciled net_pnl."""
import sys, inspect
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot

passed = []
def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    passed.append((name, cond))

print("=" * 80)
print("R10 FOCUSED TESTS")
print("=" * 80)

src_rss = inspect.getsource(UnifiedTradingBot.run_single_session)
src_cp  = inspect.getsource(UnifiedTradingBot.close_position)

print("\n[1] Return dict uses reconciled net_pnl")
ok("uses _pnl_for_return",
   "'pnl': _pnl_for_return," in src_rss)
ok("uses _pnl_pct_for_return",
   "'pnl_pct': _pnl_pct_for_return," in src_rss)
ok("win derived from _pnl_for_return",
   "'win': _pnl_for_return > 0" in src_rss)
ok("reads active_trade net_pnl",
   "active_trade.get('net_pnl')" in src_rss)
ok("reads active_trade net_pnl_pct",
   "active_trade.get('net_pnl_pct')" in src_rss)

print("\n[2] Fallback preserved when no close")
ok("fallback uses pnl local",
   "_pnl_for_return = pnl if 'pnl' in locals() else 0" in src_rss)
ok("close detected via active_trades membership",
   "if trade_id not in self.active_trades:" in src_rss)

print("\n[3] Counters and total_pnl unchanged")
ok("winning_trades counter intact",
   "self.winning_trades += 1" in src_cp)
ok("losing_trades counter intact",
   "self.losing_trades += 1" in src_cp)
ok("total_pnl uses net_pnl",
   "self.total_pnl += _pnl_for_total" in src_cp)

print("\n[4] Runtime - bot initializes cleanly")
b = UnifiedTradingBot("NIFTY")
ok("session_history empty", b.session_history == [])
ok("current_session zero", b.current_session == 0)

print("\n[5] Structural: no bare pnl in return block")
# ensure the old buggy literal is gone
ok("old buggy 'pnl': pnl literal removed",
   "'pnl': pnl if 'pnl' in locals() else 0," not in src_rss)

n_pass = sum(1 for _, c in passed if c)
n_fail = sum(1 for _, c in passed if not c)
print()
print(f"R10 FOCUSED TESTS: {n_pass}/{len(passed)} passed")
if n_fail:
    for n, c in passed:
        if not c: print(f"  FAIL: {n}")
    sys.exit(1)
print("R10 FOCUSED TESTS: ALL PASSED")
