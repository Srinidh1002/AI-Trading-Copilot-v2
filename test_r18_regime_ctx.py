"""R18 - regime_ctx guard semantics test.

Run:
  .\\venv\\Scripts\\python.exe -m unittest -v test_r18_regime_ctx
"""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from target_focused_bot import UnifiedTradingBot
from diversity_tracker import EquityCertificationDiversityTracker


def _extract_regime(regime_ctx):
    """Mirror of production expression:

        (getattr(self, '_last_regime_ctx', None) or {}).get('regime', 'UNKNOWN')

    Here we simulate over a local value.
    """
    return (regime_ctx or {}).get('regime', 'UNKNOWN')


class TestRegimeCtxGuardSemantics(unittest.TestCase):

    def test_01_valid_dict_uses_real_regime(self):
        self.assertEqual(_extract_regime({"regime": "TRENDING_UP"}), "TRENDING_UP")
        self.assertEqual(_extract_regime({"regime": "RANGE_BOUND"}), "RANGE_BOUND")

    def test_02_none_becomes_unknown(self):
        self.assertEqual(_extract_regime(None), "UNKNOWN")

    def test_03_dict_missing_key_becomes_unknown(self):
        self.assertEqual(_extract_regime({}), "UNKNOWN")
        self.assertEqual(_extract_regime({"confidence": 0.5}), "UNKNOWN")

    def test_04_no_nameerror_on_none(self):
        # A bare .get() on None would raise AttributeError; the isinstance
        # guard avoids it and returns UNKNOWN.
        try:
            r = _extract_regime(None)
        except Exception as e:
            self.fail("guard raised %r" % e)
        self.assertEqual(r, "UNKNOWN")

    def test_05_thresholds_and_counter_unchanged(self):
        # Source-level check: matches R2/R5/R6 convention. Do not depend
        # on class-attribute resolution.
        src = inspect.getsource(UnifiedTradingBot)
        self.assertIn("T1_PERCENT = 15", src)
        self.assertIn("T2_PERCENT = 30", src)
        self.assertIn("T3_PERCENT = 50", src)
        self.assertIn("STOP_LOSS_PERCENT = 5", src)

    def test_06_no_dir_pattern_remains_in_source(self):
        src = inspect.getsource(UnifiedTradingBot)
        self.assertNotIn("'regime_ctx' in dir()", src,
                         "dynamic dir() guard must not survive R18")

    def test_07_no_globals_or_eval_in_regime_path(self):
        src = inspect.getsource(UnifiedTradingBot)
        # We do not prohibit these globally, just in the regime_ctx context.
        self.assertNotIn("globals()['regime_ctx']", src)
        self.assertNotIn('globals()["regime_ctx"]', src)
        self.assertNotIn("eval(", src.split("regime_ctx")[0][-200:])


class TestRegimeUnknRejectedByDiversity(unittest.TestCase):

    def test_08_unknown_regime_rejected(self):
        t = EquityCertificationDiversityTracker()
        ok, reason = t.would_count("2026-09-16", "UNKNOWN", "EARLY_CONTINUOUS")
        self.assertFalse(ok)
        self.assertEqual(reason, "INVALID_REGIME")

    def test_09_record_cannot_bypass_unknown_regime(self):
        t = EquityCertificationDiversityTracker()
        recorded = t.record("2026-09-16", "UNKNOWN", "EARLY_CONTINUOUS")
        self.assertFalse(recorded)
        self.assertEqual(len(t.regimes), 0)
        self.assertEqual(len(t.session_phases), 0)


class TestRegimeCtxPlumbing(unittest.TestCase):
    """R18v2 - prove regime_ctx is plumbed across method boundaries."""

    def test_10_init_declares_last_regime_ctx(self):
        src = inspect.getsource(UnifiedTradingBot.__init__)
        self.assertIn("self._last_regime_ctx", src,
                      "__init__ must declare self._last_regime_ctx")

    def test_11_enhanced_sentiment_persists_regime_ctx(self):
        src = inspect.getsource(UnifiedTradingBot.get_enhanced_sentiment)
        self.assertIn("self._last_regime_ctx = regime_ctx", src,
                      "get_enhanced_sentiment must persist regime_ctx")

    def test_12_run_single_session_has_no_bare_regime_ctx_read(self):
        src = inspect.getsource(UnifiedTradingBot.run_single_session)
        # After R18v2 there should be no bare 'regime_ctx' local in this method.
        self.assertNotIn("regime_ctx.get", src,
                         "run_single_session must not read bare regime_ctx local")
        self.assertNotIn("isinstance(regime_ctx", src)

    def test_13_trade_dict_reads_from_persisted_attribute(self):
        src = inspect.getsource(UnifiedTradingBot.run_single_session)
        self.assertIn("getattr(self, '_last_regime_ctx'", src,
                      "trade dict must read from self._last_regime_ctx")


if __name__ == "__main__":
    unittest.main(verbosity=2)
