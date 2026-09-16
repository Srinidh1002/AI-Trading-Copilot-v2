"""M14A regression - exit ladder evaluates on EVERY monitoring cycle.
Tests run the actual source block extracted from mcx_paper_bot.py.
"""
import io, sys, unittest
import datetime as _dt
from datetime import time as _time

PATH = "src/mcx/mcx_paper_bot.py"
ANCHOR_START = 'entry = active["entry"]'
ANCHOR_CLOSED = 'if not closed:'
ANCHOR_SAVE = 'save_state(state)'


def extract_block():
    lines = io.open(PATH, encoding="utf-8").readlines()
    start = next(i for i, l in enumerate(lines) if ANCHOR_START in l)
    closed = next(i for i in range(start, len(lines)) if ANCHOR_CLOSED in lines[i])
    end = next(i for i in range(closed, len(lines)) if ANCHOR_SAVE in lines[i])
    block = lines[start:end + 1]
    non_blank = [l for l in block if l.strip()]
    min_ind = min(len(l) - len(l.lstrip()) for l in non_blank)
    return "".join(l[min_ind:] if l.strip() else l for l in block)


BLOCK = extract_block()


class _MockDT:
    now_value = None
    @classmethod
    def fromisoformat(cls, s): return _dt.datetime.fromisoformat(s)
    @classmethod
    def now(cls): return cls.now_value or _dt.datetime.now()


def run_case(active, ltp, mock_now=None, pm_returns=None):
    closes = []
    saves = []
    pm_calls = []
    pm_queue = list(pm_returns or [])

    def close_and_reconcile(obj, a, reason, lt, pnl, st):
        closes.append({"reason": reason, "ltp": lt, "pnl": round(pnl, 2)})

    def save_state(st): saves.append(True)

    def pm_evaluate_exit(a, lt, d, r, m):
        pm_calls.append({"peak": a.get("max_profit_pct"), "pnl": round(((lt - a["entry"]) / a["entry"]) * 100, 2), "mins": m})
        return pm_queue.pop(0) if pm_queue else (False, "HOLD", None)

    _MockDT.now_value = mock_now
    ns = {
        "active": active, "ltp": ltp,
        "datetime": _MockDT, "dtime": _time,
        "STOP_LOSS_PCT": -8.0, "T1_PCT": 15.0, "T2_PCT": 30.0, "T3_PCT": 50.0,
        "close_and_reconcile": close_and_reconcile,
        "pm_evaluate_exit": pm_evaluate_exit,
        "save_state": save_state,
        "obj": None, "state": {}, "decision": {}, "regime": {},
    }
    exec(BLOCK, ns)
    return closes, saves, pm_calls, ns["active"]


def fresh_active(**kw):
    base = {
        "entry": 100.0, "entry_time": "2026-09-15T21:12:58",
        "max_profit_pct": 0.0, "min_profit_pct": 0.0,
        "type": "CE", "strike": 100.0, "stop_loss": 92.0,
    }
    base.update(kw); return base


class TestM14A(unittest.TestCase):

    def test_A_up_move_still_evaluates_exit_ladder(self):
        # No new low; verify code reached the ladder by way of pm_evaluate_exit
        a = fresh_active(max_profit_pct=2.0, min_profit_pct=-1.0)
        closes, saves, pm, _ = run_case(a, ltp=105.0,
                                        pm_returns=[(False, "HOLD", None)])
        self.assertEqual(len(pm), 1, "pm_evaluate_exit not reached on up-move")

    def test_B_T1_exit_on_up_move(self):
        a = fresh_active(max_profit_pct=0.0, min_profit_pct=-1.0)
        closes, *_ = run_case(a, ltp=116.0)
        self.assertEqual(len(closes), 1)
        self.assertEqual(closes[0]["reason"], "T1_15%")

    def test_C_T2_exit_on_up_move(self):
        a = fresh_active(max_profit_pct=0.0, min_profit_pct=-1.0)
        closes, *_ = run_case(a, ltp=131.0)
        self.assertEqual(closes[0]["reason"], "T2_30%")

    def test_D_T3_exit_on_up_move(self):
        a = fresh_active(max_profit_pct=0.0, min_profit_pct=-1.0)
        closes, *_ = run_case(a, ltp=151.0)
        self.assertEqual(closes[0]["reason"], "T3_50%")

    def test_E_close_2310_fires_with_positive_pnl(self):
        a = fresh_active(max_profit_pct=3.0, min_profit_pct=-0.5)
        future = _dt.datetime(2026, 9, 15, 23, 11)
        closes, *_ = run_case(a, ltp=105.0, mock_now=future)
        self.assertEqual(closes[0]["reason"], "MCX_CLOSE_2310")

    def test_F_SL_fires_on_new_low(self):
        a = fresh_active(max_profit_pct=3.0, min_profit_pct=0.0)
        closes, *_ = run_case(a, ltp=91.0)  # -9%, below -8% SL
        self.assertEqual(closes[0]["reason"], "STOP_LOSS")

    def test_G_peak_drawdown_runs_every_cycle(self):
        # peak already 10%, current +5%; ladder must run and pm must decide
        a = fresh_active(max_profit_pct=10.0, min_profit_pct=-2.0)
        closes, _, pm, _ = run_case(a, ltp=105.0,
                                    pm_returns=[(True, "PEAK_DRAWDOWN_peak=10.0%_now=5.0%", None)])
        self.assertEqual(len(pm), 1)
        self.assertEqual(closes[0]["reason"], "PEAK_DRAWDOWN_peak=10.0%_now=5.0%")

    def test_H_bookkeeping_correct(self):
        a = fresh_active(max_profit_pct=5.0, min_profit_pct=-3.0)
        _, _, _, a2 = run_case(a, ltp=108.0)
        self.assertAlmostEqual(a2["max_profit_pct"], 8.0, places=2)
        self.assertAlmostEqual(a2["min_profit_pct"], -3.0, places=2)

    def test_I_no_double_save_after_close(self):
        a = fresh_active()
        closes, saves, *_ = run_case(a, ltp=151.0)
        self.assertEqual(len(closes), 1)
        self.assertEqual(len(saves), 0, "save_state must not run after close")

    def test_J_paper_safety_intact(self):
        src = io.open(PATH, encoding="utf-8").read()
        for bad in ("placeOrder", "modifyOrder", "cancelOrder",
                    "place_order", "modify_order", "cancel_order"):
            self.assertNotIn(bad, src, "no order API permitted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
