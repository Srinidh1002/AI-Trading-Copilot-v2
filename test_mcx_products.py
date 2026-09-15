"""Focused tests for MCX multi-product support. No broker calls, no live data."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def t1_supported_products():
    from mcx.mcx_version import PRODUCT_EPOCHS
    assert set(PRODUCT_EPOCHS.keys()) == {"CRUDEOILM", "GOLDM", "NATGASMINI"}


def t2_unsupported_rejected():
    from mcx.mcx_version import get_product_epochs
    assert get_product_epochs("SILVER") is None
    assert get_product_epochs("COPPER") is None
    assert get_product_epochs("GOLD") is None  # exact-match only


def t3_independent_state_paths():
    from mcx.mcx_reconcile import outcomes_path
    from mcx.mcx_learning import learn_path
    a = outcomes_path("CRUDEOILM")
    b = outcomes_path("GOLDM")
    c = outcomes_path("NATGASMINI")
    assert a != b != c != a
    assert "crudeoilm" in a and "goldm" in b and "natgasmini" in c
    assert learn_path("GOLDM") != learn_path("CRUDEOILM")


def t4_capital_independence():
    from mcx.mcx_version import PRODUCT_EPOCHS
    # CRUDEOILM must remain cert-eligible; others must not
    assert PRODUCT_EPOCHS["CRUDEOILM"]["certification_eligible"] is True
    assert PRODUCT_EPOCHS["GOLDM"]["certification_eligible"] is False
    assert PRODUCT_EPOCHS["NATGASMINI"]["certification_eligible"] is False


def t5_contract_registry():
    from mcx.mcx_contracts import PRODUCTS
    for p in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        assert p in PRODUCTS, f"{p} missing from PRODUCTS"
        assert PRODUCTS[p]["cash_multiplier"] > 0
        assert PRODUCTS[p]["strike_interval"] > 0


def t6_costs_per_product():
    from mcx.mcx_costs import net_pnl
    for p, mult in [("CRUDEOILM", 10), ("GOLDM", 10), ("NATGASMINI", 250)]:
        r = net_pnl(100.0, 110.0, 1, p, "BUY")
        assert r["status"] == "OK", f"{p} costs failed"
        # gross = (110 - 100) * mult * 1 = 10 * mult
        assert abs(r["gross_pnl"] - (10 * mult)) < 0.01, f"{p} gross mismatch: {r}"


def t7_paper_only_boundary():
    # Section rule: no placeOrder/modifyOrder/cancelOrder anywhere in src/mcx
    forbidden = ("placeOrder", "modifyOrder", "cancelOrder",
                 "place_order", "modify_order", "cancel_order")
    bad = []
    for f in os.listdir(os.path.join(_SRC, "mcx")):
        if not f.endswith(".py"):
            continue
        with open(os.path.join(_SRC, "mcx", f), encoding="utf-8") as fh:
            content = fh.read()
            for kw in forbidden:
                if kw in content:
                    bad.append((f, kw))
    assert not bad, f"Forbidden order API references: {bad}"


def t8_epoch_isolation():
    from mcx.mcx_version import PRODUCT_EPOCHS
    epochs = [PRODUCT_EPOCHS[p]["epoch"] for p in PRODUCT_EPOCHS]
    assert len(set(epochs)) == len(epochs), "epochs must be unique per product"


def t9_state_paths_distinct_per_product():
    from mcx.mcx_paper_bot import _state_path_for
    paths = [_state_path_for(p) for p in ("CRUDEOILM", "GOLDM", "NATGASMINI")]
    assert len(set(paths)) == 3, f"state paths not distinct: {paths}"
    assert "crudeoilm" in paths[0]
    assert "goldm" in paths[1]
    assert "natgasmini" in paths[2]


def t10_goldm_default_state_shape():
    from mcx.mcx_paper_bot import _default_state_for
    s = _default_state_for("GOLDM")
    assert s["product"] == "GOLDM"
    assert s["starting_capital"] == 100000
    assert s["total_trades"] == 0
    assert s["t1_hit_wins"] == 0
    assert s["sl_losses"] == 0
    assert s["total_pnl"] == 0
    assert s["active_position"] is None
    assert s["epoch"] == "GOLDM_PRECERT_V1"
    assert s["certification_eligible"] is False


def t11_natgas_default_state_shape():
    from mcx.mcx_paper_bot import _default_state_for
    s = _default_state_for("NATGASMINI")
    assert s["product"] == "NATGASMINI"
    assert s["starting_capital"] == 100000
    assert s["total_trades"] == 0
    assert s["epoch"] == "NATGASMINI_PRECERT_V1"
    assert s["certification_eligible"] is False


def t12_crude_default_state_preserves_v2_epoch():
    from mcx.mcx_paper_bot import _default_state_for
    s = _default_state_for("CRUDEOILM")
    assert s["epoch"] == "POST_PRECISION_V2"
    assert s["certification_eligible"] is True
    assert s["starting_capital"] == 100000


def t13_presession_header_product_aware():
    from mcx.mcx_presession import format_header
    for p in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        h = format_header(p)
        assert p in h, f"{p} missing from header: {h!r}"
        assert "PRE-SESSION" in h
        assert "INTELLIGENCE" in h


def t14_crude_obs_only_false():
    from mcx.mcx_paper_bot import compute_observation_only
    assert compute_observation_only("CRUDEOILM", True) is False


def t15_goldm_obs_only_true():
    from mcx.mcx_paper_bot import compute_observation_only
    assert compute_observation_only("GOLDM", True) is True


def t16_natgas_obs_only_true():
    from mcx.mcx_paper_bot import compute_observation_only
    assert compute_observation_only("NATGASMINI", True) is True


def t17_registry_authority():
    from mcx.mcx_version import is_certification_eligible
    assert is_certification_eligible("CRUDEOILM") is True
    assert is_certification_eligible("GOLDM") is False
    assert is_certification_eligible("NATGASMINI") is False
    assert is_certification_eligible("SILVER") is False


def t18_malformed_goldm_record_rejected():
    from mcx.mcx_certification import update_counters
    st = {"product": "GOLDM", "t1_hit_wins": 0, "sl_losses": 0, "_counted_trade_ids": []}
    tr = {"trade_id": "FAKE_GOLD_1", "product": "GOLDM",
          "exit_reason": "T1_15%", "net_pnl": 100.0,
          "certification_eligible": True}  # deliberately malformed
    update_counters(st, tr)
    assert st["t1_hit_wins"] == 0, f"should not count: {st}"
    assert st["sl_losses"] == 0
    assert tr.get("_counter_rejected") == "PRODUCT_NOT_CERTIFICATION_ELIGIBLE"


def t19_malformed_natgas_record_rejected():
    from mcx.mcx_certification import update_counters
    st = {"product": "NATGASMINI", "t1_hit_wins": 0, "sl_losses": 0, "_counted_trade_ids": []}
    tr = {"trade_id": "FAKE_NG_1", "product": "NATGASMINI",
          "exit_reason": "STOP_LOSS", "net_pnl": -50.0,
          "certification_eligible": True}
    update_counters(st, tr)
    assert st["t1_hit_wins"] == 0
    assert st["sl_losses"] == 0
    assert tr.get("_counter_rejected") == "PRODUCT_NOT_CERTIFICATION_ELIGIBLE"


def t20_valid_crude_record_accepted():
    from mcx.mcx_certification import update_counters
    st = {"product": "CRUDEOILM", "t1_hit_wins": 0, "sl_losses": 0, "_counted_trade_ids": []}
    tr = {"trade_id": "CRUDE_TEST_1", "product": "CRUDEOILM",
          "exit_reason": "T1_15%", "net_pnl": 100.0,
          "certification_eligible": True}
    update_counters(st, tr)
    assert st["t1_hit_wins"] == 1, f"should count: {st}"
    assert st["sl_losses"] == 0
    assert "_counter_rejected" not in tr


def t21_goldm_reconcile_not_eligible():
    from mcx.mcx_reconcile import reconcile
    pos = {"trade_id": "R_GOLD_1", "entry": 100.0, "exit": 110.0, "lots": 1,
           "_synthetic": False, "product": "GOLDM"}
    r = reconcile(pos, product="GOLDM")
    assert r.get("certification_eligible") is False, r
    assert r.get("registry_certification_eligible") is False


def t22_natgas_reconcile_not_eligible():
    from mcx.mcx_reconcile import reconcile
    pos = {"trade_id": "R_NG_1", "entry": 100.0, "exit": 110.0, "lots": 1,
           "_synthetic": False, "product": "NATGASMINI"}
    r = reconcile(pos, product="NATGASMINI")
    assert r.get("certification_eligible") is False, r
    assert r.get("registry_certification_eligible") is False


def t23_crude_reconcile_still_eligible():
    from mcx.mcx_reconcile import reconcile
    pos = {"trade_id": "R_CRUDE_1", "entry": 100.0, "exit": 110.0, "lots": 1,
           "_synthetic": False, "product": "CRUDEOILM"}
    r = reconcile(pos, product="CRUDEOILM")
    assert r.get("certification_eligible") is True, r
    assert r.get("registry_certification_eligible") is True


def run_all():
    tests = [
        t1_supported_products, t2_unsupported_rejected,
        t3_independent_state_paths, t4_capital_independence,
        t5_contract_registry, t6_costs_per_product,
        t7_paper_only_boundary, t8_epoch_isolation,
        t9_state_paths_distinct_per_product,
        t10_goldm_default_state_shape,
        t11_natgas_default_state_shape,
        t12_crude_default_state_preserves_v2_epoch,
        t13_presession_header_product_aware,
        t14_crude_obs_only_false,
        t15_goldm_obs_only_true,
        t16_natgas_obs_only_true,
        t17_registry_authority,
        t18_malformed_goldm_record_rejected,
        t19_malformed_natgas_record_rejected,
        t20_valid_crude_record_accepted,
        t21_goldm_reconcile_not_eligible,
        t22_natgas_reconcile_not_eligible,
        t23_crude_reconcile_still_eligible,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            print(f"ERR  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return passed == len(tests)


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
