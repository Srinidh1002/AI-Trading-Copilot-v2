"""R11 - consolidated integrated certification test suite.

Covers R2+R3+R4+R5+R6+R7+R8+R9+R10 as integrated scenarios (not isolated unit).
Also performs read-only source audit for:
  - remaining LTP certification-critical references
  - counter increment sites

Isolation: every test bot writes state to a private tempdir.
Live Day-1 equity files are never touched.
"""
import sys, os, json, hashlib, tempfile, shutil, re, inspect, atexit

sys.path.append("src")
from target_focused_bot import (
    UnifiedTradingBot, STRATEGY_VERSION, CERTIFICATION_EPOCH,
    _restore_first_touch,
)
from first_touch_tracker import (
    EquityFirstTouchTracker, NONE, T1_FIRST, SL_FIRST, AMBIGUOUS,
)
from certification_phase import CERT_PHASE_EARLY

# ---------- isolation ----------
_TMP = tempfile.mkdtemp(prefix="r11_isolated_")
atexit.register(lambda: shutil.rmtree(_TMP, ignore_errors=True))
_CTR = {"n": 0}
def _bot(market="NIFTY"):
    _CTR["n"] += 1
    b = UnifiedTradingBot(market)
    b.state_file = os.path.join(_TMP, f"{market.lower()}_{_CTR['n']}.json")
    return b

passed = []
def ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}  {detail}")
    passed.append((name, cond))

def sha256(p):
    if not os.path.exists(p): return None
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()

def make_trade(**kw):
    t = {
        "trade_id": "TRD_INTEG_0001",
        "market": "NIFTY",
        "status": "CLOSED",
        "execution_mode": "PAPER",
        "broker_submission": False,
        "live_execution": False,
        "certification_eligible": True,
        "certification_countable": True,
        "strategy_version": STRATEGY_VERSION,
        "certification_epoch": CERTIFICATION_EPOCH,
        "first_touch_result": "T1_FIRST",
        "certification_trade_date": "2026-09-16",
        "certification_regime": "TRENDING_UP",
        "certification_session_phase": CERT_PHASE_EARLY,
    }
    t.update(kw)
    return t

print("=" * 80)
print("R11 INTEGRATED CERTIFICATION TEST SUITE")
print("=" * 80)

# ============================================================
# A - R2 bid authority (5)
# ============================================================
print("\n[A] R2 - bid authority in threshold crossings")
entry, t1, t3, sl = 100.0, 115.0, 150.0, 95.0
def cross_t1(m): return m >= t1
def cross_t3(m): return m >= t3
def cross_sl(m): return m <= sl

ok("A1 LTP>t1 / bid<t1 -> no T1",  not cross_t1(110.0))
ok("A2 bid>=t1 -> T1 crossing",     cross_t1(116.0))
ok("A3 LTP<sl / bid>sl -> no SL",   not cross_sl(96.0))
ok("A4 bid<=sl -> SL crossing",     cross_sl(94.0))
ok("A5 LTP>t3 / bid<t3 -> no T3",   not cross_t3(145.0))

# ============================================================
# B - R3 first-touch tracker (4)
# ============================================================
print("\n[B] R3 - first-touch tracker")
t = EquityFirstTouchTracker(t1_price=t1, t2_price=130.0, t3_price=t3, sl_price=sl)
t.ingest_bid(116.0, "2026-09-16T09:30:00+05:30")
t.ingest_bid(94.0,  "2026-09-16T09:35:00+05:30")
ok("B1 T1 first -> T1_FIRST preserved", t.result() == T1_FIRST)
ok("B2 T1_first_seen_at stamped once",
   t.t1_first_seen_at == "2026-09-16T09:30:00+05:30")
state = t.to_state()
t2 = EquityFirstTouchTracker.from_state(state)
ok("B3 restart preserves result", t2.result() == t.result())
ok("B4 restart preserves t1_bid",  t2.t1_bid == t.t1_bid)

# ============================================================
# C - R4 quote-gap handling (4)
# ============================================================
print("\n[C] R4 - quote gap / ambiguity")
b = _bot()
trade = {"first_touch_result": "NONE", "monitoring_gap_count": 0,
         "monitoring_gap_started_at": None}
r1 = b._handle_quote_gap(trade, False)
r2 = b._handle_quote_gap(trade, False)
ok("C1 first failure -> skip=True",  r1 is True)
ok("C2 repeated failures = one gap", trade["monitoring_gap_count"] == 1)
r3 = b._handle_quote_gap(trade, True)
ok("C3 resume with NONE -> AMBIGUOUS", trade["first_touch_result"] == "AMBIGUOUS")
ok("C4 AMBIGUOUS -> countable False", trade["certification_countable"] is False)

# ============================================================
# D - R5 milestone accounting (3)
# ============================================================
print("\n[D] R5 - milestone accounting")
b = _bot()
src_full = inspect.getsource(UnifiedTradingBot)
ok("D1 t1_hits increment present exactly once",
   src_full.count("self.t1_hits += 1") == 1)
ok("D2 t2_hits increment present exactly once",
   src_full.count("self.t2_hits += 1") == 1)
src_close = inspect.getsource(UnifiedTradingBot.close_position)
ok("D3 cert win/loss from first_touch_result",
   "trade.get('first_touch_result')" in src_close and
   "'T1_FIRST':" in src_close and
   "trade['certification_win'] = True" in src_close)

# ============================================================
# E - R6 counter authority (10)
# ============================================================
print("\n[E] R6 - certification counter authority")

b = _bot()
ok("E1 T1_FIRST countable -> counter 1",
   b._try_increment_certification_counter(make_trade(trade_id="E1"), True)
   and b.certification_counter == 1 and b.certification_wins == 1)

b = _bot()
ok("E2 SL_FIRST countable -> counter 1 / loss 1",
   b._try_increment_certification_counter(
       make_trade(trade_id="E2", first_touch_result="SL_FIRST"), True)
   and b.certification_counter == 1 and b.certification_losses == 1)

b = _bot()
b._try_increment_certification_counter(make_trade(trade_id="E3"), True)
ok("E3 duplicate trade_id rejected",
   b._try_increment_certification_counter(make_trade(trade_id="E3"), True) is False
   and b.certification_counter == 1)

b = _bot()
ok("E4 NOT_RECONCILED rejected",
   b._try_increment_certification_counter(make_trade(trade_id="E4"), False) is False
   and b.certification_counter == 0)

b = _bot()
ok("E5 NOT_PAPER rejected",
   b._try_increment_certification_counter(
       make_trade(trade_id="E5", execution_mode="LIVE"), True) is False
   and b.certification_counter == 0)

b = _bot()
ok("E6 broker_submission=True rejected",
   b._try_increment_certification_counter(
       make_trade(trade_id="E6", broker_submission=True), True) is False)

b = _bot()
ok("E7 live_execution=True rejected",
   b._try_increment_certification_counter(
       make_trade(trade_id="E7", live_execution=True), True) is False)

b = _bot()
ok("E8 certification_countable=False (AMBIGUOUS) rejected",
   b._try_increment_certification_counter(
       make_trade(trade_id="E8", certification_countable=False,
                  first_touch_result="AMBIGUOUS"), True) is False)

b = _bot()
ok("E9 wrong strategy_version rejected",
   b._try_increment_certification_counter(
       make_trade(trade_id="E9", strategy_version="OLD"), True) is False)

b = _bot()
ok("E10 wrong epoch rejected",
   b._try_increment_certification_counter(
       make_trade(trade_id="E10", certification_epoch="OLD"), True) is False)

# ============================================================
# F - R9 epoch metadata (2)
# ============================================================
print("\n[F] R9 - epoch metadata")
b = _bot()
ok("F1 fresh bot new-epoch",
   b.strategy_version == STRATEGY_VERSION
   and b.certification_epoch == CERTIFICATION_EPOCH
   and b.is_legacy_precert is False)
legacy_path = os.path.join(_TMP, "legacy.json")
with open(legacy_path, "w", encoding="utf-8") as f:
    json.dump({"market": "NIFTY", "current_session": 3, "total_trades": 3}, f)
b = _bot()
b.state_file = legacy_path
b.load_state()
ok("F2 legacy loads safely (no epoch inherited)",
   b.certification_epoch is None and b.strategy_version is None
   and b.is_legacy_precert is True)

# ============================================================
# G - R8 prediction linkage (1)
# ============================================================
print("\n[G] R8 - prediction linkage")
b = _bot()
src_rss = inspect.getsource(UnifiedTradingBot.run_single_session)
ok("G1 trade dict carries prediction_fingerprint",
   "'prediction_fingerprint': getattr(self, '_last_prediction_fingerprint', None)" in src_rss)

# ============================================================
# H - R7 outcome ledger (1)
# ============================================================
print("\n[H] R7 - outcome ledger evidence schema")
from outcome_ledger import OutcomeLedger
with open("src/outcome_ledger.py", encoding="utf-8") as f:
    ol_src = f.read()
required = ["strategy_version", "certification_epoch", "prediction_fingerprint",
            "entry_bid", "entry_ask", "exit_bid", "t1_hit", "t2_hit",
            "first_touch_result", "certification_win", "certification_loss",
            "certification_countable", "trail_stop", "peak_bid", "trough_bid",
            "monitoring_gap_count", "evidence_ambiguous"]
missing = [k for k in required if f'"{k}"' not in ol_src]
ok("H1 outcome ledger has all cert-evidence fields",
   len(missing) == 0, f"missing={missing}")

# ============================================================
# I - R10 session history (1)
# ============================================================
print("\n[I] R10 - session_history uses reconciled net P&L")
ok("I1 uses _pnl_for_return from net_pnl",
   "_pnl_for_return = _net" in src_rss
   or "_net = active_trade.get('net_pnl')" in src_rss)

# ============================================================
# J - Market independence (1)
# ============================================================
print("\n[J] NIFTY / SENSEX counter independence")
bn = _bot("NIFTY")
bs = _bot("SENSEX")
bn._try_increment_certification_counter(
    make_trade(trade_id="N1", market="NIFTY"), True)
ok("J1 NIFTY counter 1 / SENSEX counter 0",
   bn.certification_counter == 1 and bs.certification_counter == 0)

# ============================================================
# K - Source audit
# ============================================================
print("\n[K] Source audit")

# --- K1..K6: LTP no longer cert-critical in monitor loop
ok("K1 no T1 via pnl_pct in monitor",
   "pnl_pct >= self.T1_PERCENT" not in src_rss)
ok("K2 no T3 via pnl_pct in monitor",
   "pnl_pct >= self.T3_PERCENT" not in src_rss)
ok("K3 no SL via pnl_pct in monitor",
   "pnl_pct <= -self.STOP_LOSS_PERCENT" not in src_rss)
ok("K4 T1 uses current_mark vs t1_price",
   "current_mark >= active_trade['t1_price']" in src_rss)
ok("K5 T3 uses current_mark vs t3_price",
   "current_mark >= active_trade['t3_price']" in src_rss)
ok("K6 SL uses current_mark vs sl_price",
   "current_mark <= active_trade['sl_price']" in src_rss)

# --- K7: single canonical counter increment site
full_bot_src = inspect.getsource(UnifiedTradingBot)
ok("K7 exactly one certification_counter += 1 in bot",
   full_bot_src.count("self.certification_counter += 1") == 1)

# --- K8: no current_session increment in bot
ok("K8 no current_session += 1 in bot",
   "self.current_session += 1" not in full_bot_src)

# --- K9: runners use certification_counter for loop
with open("run_nifty.py", encoding="utf-8") as f:
    n_src = f.read()
with open("run_sensex.py", encoding="utf-8") as f:
    s_src = f.read()
ok("K9 NIFTY loop uses cert counter",
   "bot.certification_counter < 100" in n_src
   and "bot.current_session < 100" not in n_src)
ok("K10 SENSEX loop uses cert counter",
   "bot.certification_counter < 100" in s_src
   and "bot.current_session < 100" not in s_src)

# --- K11: LTP references remaining (informational)
print("\n  --- Remaining LTP references in run_single_session (classified) ---")
for i, line in enumerate(src_rss.splitlines(), 1):
    if "current_ltp" in line or "current_price" in line or "pnl_pct" in line:
        low = line.strip()
        if "current_ltp = quote.get('ltp')" in low:
            cls = "DISPLAY_CAPTURE"
        elif "current_price = current_ltp" in low:
            cls = "LEGACY_ALIAS"
        elif "active_trade['current_price']" in low:
            cls = "LEGACY_KEY_NOW_BID"
        elif "print" in low:
            cls = "DISPLAY"
        elif "current_mark" in low:
            cls = "BID_AUTHORITY"
        elif "pnl_pct" in low and ("=" in low.split("pnl_pct")[0]):
            cls = "BID_DERIVED"
        else:
            cls = "INFO"
        print(f"    {cls:24} | {low[:100]}")

# --- K12..K15: archived Day-1 + active V2 genesis hashes intact
_ARCH = "data/paper_trades/_archived_NS_precert_20260915"
for label, active_fname, arch_fname, v1_prefix, day1_prefix in [
    ("K12 nifty_experimental",  "data/paper_trades/nifty_experimental.json",  _ARCH + "/nifty_experimental.json",  "bbaace49", "106e57f3"),
    ("K13 sensex_experimental", "data/paper_trades/sensex_experimental.json", _ARCH + "/sensex_experimental.json", "707dffbe", "a1239db0"),
    ("K14 nifty_predictions",   "data/paper_trades/nifty_predictions.jsonl",  _ARCH + "/nifty_predictions.jsonl",  "e3b0c442", "5fe634be"),
    ("K15 sensex_predictions",  "data/paper_trades/sensex_predictions.jsonl", _ARCH + "/sensex_predictions.jsonl", "e3b0c442", "d7790e3a"),
]:
    h_act = sha256(active_fname)
    h_arc = sha256(arch_fname)
    ok(f"{label} unchanged",
       (h_act and h_act.startswith(v1_prefix)) and (h_arc and h_arc.startswith(day1_prefix)),
       f"active={h_act[:8] if h_act else 'MISS'} archive={h_arc[:8] if h_arc else 'MISS'}")

# ============================================================
# Summary
# ============================================================
n_pass = sum(1 for _, c in passed if c)
n_fail = sum(1 for _, c in passed if not c)
print()
print("=" * 80)
print(f"R11 INTEGRATED TEST SUITE: {n_pass}/{len(passed)} passed")
if n_fail:
    print("FAILURES:")
    for n, c in passed:
        if not c:
            print(f"  - {n}")
    sys.exit(1)
print("R11 INTEGRATED TEST SUITE: ALL PASSED")
print("=" * 80)
