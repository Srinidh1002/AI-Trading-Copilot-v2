import os
import sys
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "src"))

r"""R16 certification session-phase tests.

Run:
  .\venv\Scripts\python.exe -m unittest -v test_r16_cert_phase
"""
import glob
import os
import unittest
from datetime import date, datetime, timedelta

from market_phase import MarketPhaseEngine
from certification_phase import (
    classify_certification_session_phase,
    PHASE_BOUNDARIES,
    CERT_PHASE_EARLY,
    CERT_PHASE_MID,
    CERT_PHASE_LATE,
    CERT_PHASE_UNKNOWN,
    CERT_PHASES_VALID,
)
from diversity_tracker import EquityCertificationDiversityTracker


_TEST_DATE = date(2026, 9, 16)  # Wednesday, not in NSE_HOLIDAYS_2026


def _dt(h, m, s=0):
    return datetime(_TEST_DATE.year, _TEST_DATE.month, _TEST_DATE.day, h, m, s)


class TestBuckets(unittest.TestCase):

    def setUp(self):
        self.engine = MarketPhaseEngine("NIFTY")

    def _classify(self, h, m, s=0):
        return classify_certification_session_phase(
            dt=_dt(h, m, s), engine=self.engine)

    def test_01_pre_open_is_unknown(self):
        self.assertEqual(self._classify(8, 30), CERT_PHASE_UNKNOWN)

    def test_02_before_continuous_is_unknown(self):
        self.assertEqual(self._classify(9, 14), CERT_PHASE_UNKNOWN)

    def test_03_continuous_start_is_early(self):
        self.assertEqual(self._classify(9, 15), CERT_PHASE_EARLY)

    def test_04_last_minute_of_early_is_early(self):
        self.assertEqual(self._classify(11, 14), CERT_PHASE_EARLY)

    def test_05_mid_bucket_start(self):
        self.assertEqual(self._classify(11, 15), CERT_PHASE_MID)

    def test_06_last_minute_of_mid_is_mid(self):
        self.assertEqual(self._classify(13, 14), CERT_PHASE_MID)

    def test_07_late_bucket_start(self):
        self.assertEqual(self._classify(13, 15), CERT_PHASE_LATE)

    def test_08_last_minute_before_cutoff_is_late(self):
        self.assertEqual(self._classify(15, 14), CERT_PHASE_LATE)

    def test_09_entry_cutoff_is_unknown(self):
        self.assertEqual(self._classify(15, 15), CERT_PHASE_UNKNOWN)

    def test_10_final_exit_is_unknown(self):
        self.assertEqual(self._classify(15, 28), CERT_PHASE_UNKNOWN)

    def test_11_determinism(self):
        a = self._classify(10, 30)
        b = self._classify(10, 30)
        self.assertEqual(a, b)
        self.assertEqual(a, CERT_PHASE_EARLY)

    def test_12_restart_stability(self):
        e2 = MarketPhaseEngine("NIFTY")
        a = classify_certification_session_phase(dt=_dt(14, 0), engine=e2)
        b = classify_certification_session_phase(dt=_dt(14, 0), engine=e2)
        self.assertEqual(a, b)
        self.assertEqual(a, CERT_PHASE_LATE)

    def test_13_two_phases_reachable_during_can_enter(self):
        d1 = _dt(10, 0)
        d2 = _dt(14, 0)
        self.assertTrue(self.engine.can_enter(d1))
        self.assertTrue(self.engine.can_enter(d2))
        p1 = classify_certification_session_phase(dt=d1, engine=self.engine)
        p2 = classify_certification_session_phase(dt=d2, engine=self.engine)
        self.assertIn(p1, CERT_PHASES_VALID)
        self.assertIn(p2, CERT_PHASES_VALID)
        self.assertNotEqual(p1, p2)

    def test_14_no_gap_no_overlap_full_window(self):
        cs = MarketPhaseEngine.CONTINUOUS_START
        ec = MarketPhaseEngine.NEW_ENTRY_CUTOFF
        start_min = cs.hour * 60 + cs.minute
        end_min = ec.hour * 60 + ec.minute
        seen = {CERT_PHASE_EARLY: 0, CERT_PHASE_MID: 0, CERT_PHASE_LATE: 0}
        total = 0
        for mm in range(start_min, end_min):
            h = mm // 60
            m = mm % 60
            bucket = classify_certification_session_phase(
                dt=_dt(h, m), engine=self.engine)
            self.assertIn(bucket, CERT_PHASES_VALID,
                          "unexpected bucket %r at %02d:%02d" % (bucket, h, m))
            seen[bucket] += 1
            total += 1
        self.assertEqual(total, 360)
        self.assertEqual(seen[CERT_PHASE_EARLY], 120)
        self.assertEqual(seen[CERT_PHASE_MID], 120)
        self.assertEqual(seen[CERT_PHASE_LATE], 120)

    def test_15_market_phase_truth_table_unchanged(self):
        e = self.engine
        self.assertFalse(e.can_enter(_dt(9, 0)))
        self.assertFalse(e.can_enter(_dt(9, 14)))
        self.assertTrue(e.can_enter(_dt(9, 15)))
        self.assertTrue(e.can_enter(_dt(15, 14)))
        self.assertFalse(e.can_enter(_dt(15, 15)))
        self.assertFalse(e.can_enter(_dt(15, 30)))

    def test_16_entry_gate_source_unchanged(self):
        src_path = os.path.join("src", "market_phase.py")
        self.assertTrue(os.path.isfile(src_path),
                        "market_phase.py not found at %s" % src_path)
        with open(src_path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn('return ("CONTINUOUS", True, True', text)

    def test_17_mcx_modules_present(self):
        mcx_dir = os.path.join("src", "mcx")
        if not os.path.isdir(mcx_dir):
            self.skipTest("MCX directory not present in this checkout")
        py_files = glob.glob(os.path.join(mcx_dir, "*.py"))
        self.assertGreaterEqual(len(py_files), 40,
            "Expected >=40 MCX modules, found %d" % len(py_files))
        for name in ("mcx_paper_bot.py", "mcx_identity.py", "mcx_contracts.py"):
            self.assertTrue(
                os.path.isfile(os.path.join(mcx_dir, name)),
                "MCX module missing: %s" % name)


class TestDiversityValidation(unittest.TestCase):

    def setUp(self):
        self.t = EquityCertificationDiversityTracker()

    def test_18_unknown_phase_rejected_by_would_count(self):
        ok, reason = self.t.would_count(
            "2026-09-16", "TRENDING_UP", "UNKNOWN")
        self.assertFalse(ok)
        self.assertEqual(reason, "INVALID_SESSION_PHASE")

    def test_19_blank_or_none_phase_rejected(self):
        for bad in ("", None):
            ok, reason = self.t.would_count(
                "2026-09-16", "TRENDING_UP", bad)
            self.assertFalse(ok, "expected reject for phase=%r" % (bad,))
            self.assertEqual(reason, "INVALID_SESSION_PHASE")

    def test_20_unknown_regime_rejected(self):
        ok, reason = self.t.would_count(
            "2026-09-16", "UNKNOWN", "EARLY_CONTINUOUS")
        self.assertFalse(ok)
        self.assertEqual(reason, "INVALID_REGIME")

    def test_21_blank_or_none_regime_rejected(self):
        for bad in ("", None):
            ok, reason = self.t.would_count(
                "2026-09-16", bad, "EARLY_CONTINUOUS")
            self.assertFalse(ok, "expected reject for regime=%r" % (bad,))
            self.assertEqual(reason, "INVALID_REGIME")

    def test_22_record_rejects_invalid_inputs(self):
        self.assertTrue(self.t.record(
            "2026-09-16", "TRENDING_UP", "EARLY_CONTINUOUS"))
        self.assertEqual(len(self.t.session_phases), 1)
        self.assertEqual(len(self.t.regimes), 1)
        self.assertFalse(self.t.record(
            "2026-09-16", "TRENDING_UP", "UNKNOWN"))
        self.assertFalse(self.t.record(
            "2026-09-16", "UNKNOWN", "EARLY_CONTINUOUS"))
        self.assertFalse(self.t.record(
            "2026-09-16", "TRENDING_UP", ""))
        self.assertFalse(self.t.record(
            "2026-09-16", "", "EARLY_CONTINUOUS"))
        self.assertFalse(self.t.record(
            "2026-09-16", None, "EARLY_CONTINUOUS"))
        self.assertFalse(self.t.record(
            "2026-09-16", "TRENDING_UP", None))
        self.assertEqual(len(self.t.session_phases), 1)
        self.assertEqual(len(self.t.regimes), 1)
        self.assertEqual(self.t.countable_by_day.get("2026-09-16"), 1)

    def test_23_timezone_aware_and_ist_naive_equivalent(self):
        try:
            from zoneinfo import ZoneInfo
            ist = ZoneInfo("Asia/Kolkata")
            utc = ZoneInfo("UTC")
        except Exception:
            self.skipTest("zoneinfo not available")
        naive_ist_1000 = _dt(10, 0)
        aware_ist_1000 = naive_ist_1000.replace(tzinfo=ist)
        aware_utc_same_instant = aware_ist_1000.astimezone(utc)
        e = MarketPhaseEngine("NIFTY")
        a = classify_certification_session_phase(
            dt=naive_ist_1000, engine=e)
        b = classify_certification_session_phase(
            dt=aware_ist_1000, engine=e)
        c = classify_certification_session_phase(
            dt=aware_utc_same_instant, engine=e)
        self.assertEqual(a, b)
        self.assertEqual(a, c)
        self.assertEqual(a, CERT_PHASE_EARLY)

    def test_24_boundaries_derived_from_engine_constants(self):
        cs = MarketPhaseEngine.CONTINUOUS_START
        ec = MarketPhaseEngine.NEW_ENTRY_CUTOFF
        cs_min = cs.hour * 60 + cs.minute
        ec_min = ec.hour * 60 + ec.minute
        window = ec_min - cs_min
        self.assertEqual(window % 3, 0,
            "Window %d does not divide into 3" % window)
        third = window // 3
        base = datetime(2000, 1, 1, cs.hour, cs.minute)
        b1_end = (base + timedelta(minutes=third)).time()
        b2_end = (base + timedelta(minutes=third * 2)).time()
        self.assertEqual(PHASE_BOUNDARIES[CERT_PHASE_EARLY], (cs, b1_end))
        self.assertEqual(PHASE_BOUNDARIES[CERT_PHASE_MID],   (b1_end, b2_end))
        self.assertEqual(PHASE_BOUNDARIES[CERT_PHASE_LATE],  (b2_end, ec))


if __name__ == "__main__":
    unittest.main(verbosity=2)
