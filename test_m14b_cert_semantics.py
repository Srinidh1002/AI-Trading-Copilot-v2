"""M14B regression - first-touch authority for certification."""
import sys, unittest
sys.path.insert(0, "src")
from mcx.mcx_certification import classify_win, update_counters


def _trade(ft=None, reason="", net=0.0, product="CRUDEOILM"):
    t = {"trade_id": "T_" + str(ft) + reason, "product": product,
         "certification_eligible": True, "net_pnl": net}
    if ft is not None:
        t["first_touch_result"] = ft
    t["exit_reason"] = reason
    return t


class TestM14B(unittest.TestCase):

    def test_T1_FIRST_with_realized_loss_is_win(self):
        t = _trade(ft="T1_FIRST", reason="PEAK_DRAWDOWN_peak=54.4%_now=-6.1%", net=-360.83)
        self.assertEqual(classify_win(t), "T1_WIN")
        s = {}
        update_counters(s, t)
        self.assertEqual(s["t1_hit_wins"], 1)
        self.assertEqual(s["sl_losses"], 0)

    def test_T1_FIRST_with_realized_profit_is_win(self):
        t = _trade(ft="T1_FIRST", reason="T1_15%", net=500.0)
        self.assertEqual(classify_win(t), "T1_WIN")

    def test_SL_FIRST_with_realized_loss_is_loss(self):
        t = _trade(ft="SL_FIRST", reason="STOP_LOSS", net=-400.0)
        self.assertEqual(classify_win(t), "SL_LOSS")
        s = {}
        update_counters(s, t)
        self.assertEqual(s["sl_losses"], 1)

    def test_SL_FIRST_with_realized_profit_is_still_loss(self):
        t = _trade(ft="SL_FIRST", reason="T3_50%", net=999.0)
        self.assertEqual(classify_win(t), "SL_LOSS")

    def test_ambiguous_is_noncountable(self):
        t = _trade(ft="AMBIGUOUS", reason="T1_15%", net=100.0)
        self.assertEqual(classify_win(t), "NONCOUNTABLE")
        s = {}
        update_counters(s, t)
        self.assertEqual(s["t1_hit_wins"], 0)
        self.assertEqual(s["sl_losses"], 0)
        self.assertIn(t["trade_id"], s.get("_cert_rejected_trade_ids", []))

    def test_missing_first_touch_is_noncountable(self):
        t = _trade(ft=None, reason="T1_15%", net=100.0)
        self.assertEqual(classify_win(t), "NONCOUNTABLE")

    def test_duplicate_no_double_count(self):
        t = _trade(ft="T1_FIRST")
        s = {}
        update_counters(s, t); update_counters(s, t)
        self.assertEqual(s["t1_hit_wins"], 1)

    def test_wrong_epoch_like_ineligible_is_rejected(self):
        t = _trade(ft="T1_FIRST")
        t["certification_eligible"] = False
        s = {}
        update_counters(s, t)
        self.assertEqual(s["t1_hit_wins"], 0)
        self.assertEqual(t.get("_counter_rejected"), "RECORD_NOT_CERTIFICATION_ELIGIBLE")

    def test_net_pnl_no_longer_cert_authority(self):
        # SL_FIRST + profit must NOT become WIN
        t = _trade(ft="SL_FIRST", net=10000.0)
        self.assertEqual(classify_win(t), "SL_LOSS")

    def test_realized_pnl_still_present(self):
        t = _trade(ft="T1_FIRST", net=123.45)
        self.assertEqual(t["net_pnl"], 123.45)


if __name__ == "__main__":
    unittest.main(verbosity=2)
