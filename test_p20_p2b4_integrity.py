"""P20 P2B.4 - integrity regression tests (A-G).

Offline. Deterministic. No broker/network calls.
"""
import inspect
import io
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "src"))


class _FailLedger:
    def __init__(self):
        self.calls = 0
    def build_record(self, **kw):
        return dict(kw, fingerprint="fp_" + str(self.calls))
    def record(self, rec):
        self.calls += 1
        return False


class _OkLedger:
    def __init__(self):
        self.records = []
    def build_record(self, **kw):
        return dict(kw, fingerprint="fp_ok_" + str(len(self.records)))
    def record(self, rec):
        self.records.append(rec)
        return True


def _bot_stub(**attrs):
    from target_focused_bot import UnifiedTradingBot
    b = UnifiedTradingBot.__new__(UnifiedTradingBot)
    b.market = "NIFTY"
    b._last_prediction_fingerprint = "STALE_SENTINEL"
    b.decision_state = "UNKNOWN"
    b.prediction_ledger = _OkLedger()
    for k, v in attrs.items():
        setattr(b, k, v)
    return b


# ---------------- A ----------------
class TestA_RecordFalseFailsClosed(unittest.TestCase):
    def test_a1_helper_returns_false_on_record_false(self):
        b = _bot_stub()
        b.prediction_ledger = _FailLedger()
        ok = b._persist_prediction(
            bias="BULLISH", bias_confidence="STRONG",
            readiness="READY", action="BUY_CALL",
            blockers=[])
        self.assertFalse(ok)
        self.assertIsNone(b._last_prediction_fingerprint)

    def test_a2_source_fail_closed_at_composer(self):
        from target_focused_bot import UnifiedTradingBot
        src = inspect.getsource(UnifiedTradingBot.get_enhanced_sentiment)
        self.assertIn("BLOCKED_LEDGER_PERSISTENCE", src)
        self.assertIn("if not _persist_ok:", src)

    def test_a3_no_stale_fingerprint_leaks_on_failure(self):
        b = _bot_stub()
        b.prediction_ledger = _FailLedger()
        b._persist_prediction(bias="BULLISH", bias_confidence="STRONG",
                              readiness="READY", action="BUY_CALL",
                              blockers=[])
        self.assertIsNone(b._last_prediction_fingerprint)


# ---------------- B ----------------
class TestB_FlatPathPersistsOnce(unittest.TestCase):
    def test_b1_source_contains_flat_persistence(self):
        from target_focused_bot import UnifiedTradingBot
        src = inspect.getsource(UnifiedTradingBot.get_enhanced_sentiment)
        self.assertEqual(src.count("MARKET_FLAT_RANGE_BOUND"), 1)

    def test_b2_flat_abstention_writes_one_row_with_real_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            from prediction_ledger import PredictionLedger
            led = PredictionLedger("NIFTY", base_dir=td)
            b = _bot_stub()
            b.prediction_ledger = led
            # P20 P2B.4a - flat path must persist REAL nonzero evidence,
            # not zeros.
            ok = b._persist_prediction(
                bias="NEUTRAL", bias_confidence="WEAK",
                readiness="WAIT", action="WAIT",
                blockers=["MARKET_FLAT_RANGE_BOUND"],
                bull_score=1.6, bear_score=0.3,
                bull_pillars=2, bear_pillars=1,
                coverage_pct=42.857, spot=100.0, spot_freshness="OK",
                regime="RANGE_BOUND")
            self.assertTrue(ok)
            p = os.path.join(td, "nifty_predictions.jsonl")
            self.assertTrue(os.path.isfile(p))
            with io.open(p, encoding="utf-8") as f:
                lines = [l for l in f.read().splitlines() if l.strip()]
            self.assertEqual(len(lines), 1, "exactly one row must be written")
            rec = json.loads(lines[0])
            self.assertIn("MARKET_FLAT_RANGE_BOUND", rec.get("blockers", []))
            # Real evidence preserved - the crucial assertion for P2B.4a
            self.assertEqual(rec.get("bull_score"), 1.6,
                             "flat abstention must persist actual bull_score")
            self.assertEqual(rec.get("bear_score"), 0.3,
                             "flat abstention must persist actual bear_score")
            self.assertEqual(rec.get("bull_pillars"), 2,
                             "flat abstention must persist actual bull_pillars")
            self.assertEqual(rec.get("bear_pillars"), 1,
                             "flat abstention must persist actual bear_pillars")
            cov = rec.get("evidence_coverage_pct")
            self.assertIsNotNone(cov)
            # Real ledger rounds to 1 decimal; assert nonzero and near expected
            self.assertGreater(float(cov), 40.0,
                               "flat abstention must persist nonzero actual coverage")
            self.assertLess(float(cov), 45.0)


# ---------------- C ----------------
class TestC_StockIncompletePersistsOnce(unittest.TestCase):
    def test_c1_source_contains_stock_persistence(self):
        from target_focused_bot import UnifiedTradingBot
        src = inspect.getsource(UnifiedTradingBot.get_enhanced_sentiment)
        self.assertEqual(src.count("STOCK_EVIDENCE_INCOMPLETE"), 1)

    def test_c2_stock_abstention_writes_one_row(self):
        with tempfile.TemporaryDirectory() as td:
            from prediction_ledger import PredictionLedger
            led = PredictionLedger("NIFTY", base_dir=td)
            b = _bot_stub()
            b.prediction_ledger = led
            ok = b._persist_prediction(
                bias="NEUTRAL", bias_confidence="WEAK",
                readiness="WAIT", action="WAIT",
                blockers=["STOCK_EVIDENCE_INCOMPLETE"])
            self.assertTrue(ok)
            p = os.path.join(td, "nifty_predictions.jsonl")
            lines = [l for l in io.open(p, encoding="utf-8").read().splitlines() if l.strip()]
            self.assertEqual(len(lines), 1)


# ---------------- D ----------------
class TestD_McxEntryVerifierError(unittest.TestCase):
    def test_d1_entry_exception_adds_rejection(self):
        import mcx.mcx_exec_countability as cap
        orig = cap._evidence_verify_one
        def fake(trade, quote_id, prefix, product, date_iso=None):
            if prefix == "ENTRY":
                raise RuntimeError("boom")
            return []
        cap._evidence_verify_one = fake
        try:
            tr = {
                "execution_mode": "PAPER", "market_origin": "REAL_MARKET",
                "quote_origin": "REAL_PROVIDER",
                "entry_fill_method": "DEPTH_VWAP",
                "exit_fill_method": "DEPTH_VWAP",
                "entry_quote_id": "Q1", "exit_quote_id": "Q2",
                "certification_eligible": True,
                "product": "CRUDEOILM", "terminal": True, "reconciled": True}
            ok, reasons = cap.is_countable(tr, "CRUDEOILM")
        finally:
            cap._evidence_verify_one = orig
        self.assertFalse(ok)
        self.assertIn("ENTRY_QUOTE_EVIDENCE_VERIFICATION_ERROR", reasons)


# ---------------- E ----------------
class TestE_McxExitVerifierError(unittest.TestCase):
    def test_e1_exit_exception_adds_rejection(self):
        import mcx.mcx_exec_countability as cap
        orig = cap._evidence_verify_one
        def fake(trade, quote_id, prefix, product, date_iso=None):
            if prefix == "EXIT":
                raise RuntimeError("boom")
            return []
        cap._evidence_verify_one = fake
        try:
            tr = {
                "execution_mode": "PAPER", "market_origin": "REAL_MARKET",
                "quote_origin": "REAL_PROVIDER",
                "entry_fill_method": "DEPTH_VWAP",
                "exit_fill_method": "DEPTH_VWAP",
                "entry_quote_id": "Q1", "exit_quote_id": "Q2",
                "certification_eligible": True,
                "product": "CRUDEOILM", "terminal": True, "reconciled": True}
            ok, reasons = cap.is_countable(tr, "CRUDEOILM")
        finally:
            cap._evidence_verify_one = orig
        self.assertFalse(ok)
        self.assertIn("EXIT_QUOTE_EVIDENCE_VERIFICATION_ERROR", reasons)


# ---------------- F ----------------
class TestF_BidBasedExitValidBid(unittest.TestCase):
    def test_f1_valid_bid_produces_exit(self):
        from target_focused_bot import UnifiedTradingBot

        class _Cap:
            slippage_pct = 0.5  # deterministic for test

        b = UnifiedTradingBot.__new__(UnifiedTradingBot)
        b.capital_engine = _Cap()
        entry, bid, lot = 100.0, 110.0, 10
        exit_px, pnl, pnl_pct = b._bid_based_exit(entry, bid, lot)
        # Exit must be <= bid (adverse slippage); must be strictly less
        # than bid by the configured slippage (proves bid-derived, not LTP)
        self.assertLess(exit_px, bid)
        self.assertAlmostEqual(exit_px, 110.0 - 110.0 * 0.005, places=2)
        self.assertAlmostEqual(pnl, (exit_px - entry) * lot, places=6)
        self.assertAlmostEqual(pnl_pct, ((exit_px - entry) / entry) * 100, places=6)


# ---------------- G ----------------
class TestG_BidBasedExitMissingBid(unittest.TestCase):
    def test_g1_none_bid_raises(self):
        from target_focused_bot import UnifiedTradingBot
        b = UnifiedTradingBot.__new__(UnifiedTradingBot)
        with self.assertRaises(RuntimeError) as ctx:
            b._bid_based_exit(100.0, None, 10)
        self.assertIn("EXIT_BID_UNAVAILABLE", str(ctx.exception))

    def test_g2_zero_bid_raises(self):
        from target_focused_bot import UnifiedTradingBot
        b = UnifiedTradingBot.__new__(UnifiedTradingBot)
        with self.assertRaises(RuntimeError) as ctx:
            b._bid_based_exit(100.0, 0, 10)
        self.assertIn("EXIT_BID_UNAVAILABLE", str(ctx.exception))

    def test_g3_no_ltp_fallback_in_source(self):
        from target_focused_bot import UnifiedTradingBot
        src = inspect.getsource(UnifiedTradingBot._bid_based_exit)
        self.assertNotIn("fallback_ltp", src)
        self.assertNotIn("using LTP", src)


# ---------------- A4: End-to-end fail-closed on composer path ----------------
class TestA4_EndToEndFailClosed(unittest.TestCase):
    """P20 P2B.4a - behavioral proof that a directional composer decision
    is neutralized when prediction_ledger.record() returns False.

    Executes the actual get_enhanced_sentiment control flow. All external
    dependencies are stubbed; no network/broker calls are made.
    """

    def _make_bot(self):
        from target_focused_bot import UnifiedTradingBot

        class _BuyComposer:
            def compose(self, ctx):
                return {
                    'bias': 'BULLISH',
                    'bias_confidence': 'STRONG',
                    'readiness': 'READY',
                    'action': 'BUY_CALL',
                    'blockers': [],
                }

        class _FailLedger:
            def build_record(self, **kw):
                return dict(kw, fingerprint="fp_test")
            def record(self, rec):
                return False

        class _EmptyTracker:
            def describe(self, **kw):
                return {}

        class _MP:
            def describe(self):
                return {'phase': 'CONTINUOUS', 'can_enter': True,
                        'can_exit': True, 'note': '', 'market': 'NIFTY'}

        b = UnifiedTradingBot.__new__(UnifiedTradingBot)
        b.market = "NIFTY"
        b._last_prediction_fingerprint = None
        b.decision_state = "UNKNOWN"
        b.previous_spot = 100.0
        # Do NOT pre-set _session_open_price / _day_open_loaded; the
        # production code assigns _phase inside the
        # `if not hasattr(self, '_session_open_price'):` block.
        b._last_spot_freshness = {'status': 'OK', 'age_seconds': 1.0}
        b._last_chain = {'pcr_oi': 1.0}
        b._last_stock_data = []
        b.contract_index = {}
        b.ws_feed = None
        b.market_intel = None
        b.breadth_engine = None
        b.vix_engine = None
        b.fii_dii_engine = None
        b.prev_day_engine = None
        b.external_intel = None
        b.calendar_engine = None
        b.news_engine = None
        b.vwap_tracker = _EmptyTracker()
        b.or_tracker = _EmptyTracker()
        b.market_phase = _MP()
        b.decision_composer = _BuyComposer()
        b.prediction_ledger = _FailLedger()

        b.get_market_sentiment = lambda spot, options: ('BULLISH', 0.9)
        b.analyze_top_stocks = lambda: (10, 0, 'BULLISH')
        b.get_day_open = lambda spot: (100.0, 'OK')

        return b

    def test_a4_composer_path_fails_closed_on_record_false(self):
        b = self._make_bot()
        result = b.get_enhanced_sentiment(spot=100.5, options=[{'strike': 100}])
        self.assertEqual(
            result, 'NEUTRAL',
            "directional composer result must be neutralized when "
            "prediction ledger persistence fails")
        self.assertEqual(b.decision_state, 'BLOCKED_LEDGER_PERSISTENCE')
        self.assertIsNone(
            b._last_prediction_fingerprint,
            "no fingerprint may be assigned on persistence failure")

    def test_a5_source_contains_fail_closed_return(self):
        from target_focused_bot import UnifiedTradingBot
        src = inspect.getsource(UnifiedTradingBot.get_enhanced_sentiment)
        self.assertIn("BLOCKED_LEDGER_PERSISTENCE", src)
        self.assertIn("if not _persist_ok:", src)
        self.assertIn("return 'NEUTRAL'", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
