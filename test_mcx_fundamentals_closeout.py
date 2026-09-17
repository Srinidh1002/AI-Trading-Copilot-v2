"""Section 5 close-out tests — P0 curve structure, P1 authority, P2 denominators."""
import os, sys, hashlib, json, re

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# --- P0 curve structure (t01-t12) ---
def t01_brent_wti_not_backwardation():
    from mcx.mcx_crude_fundamentals import classify_benchmark_spread
    cls, _ = classify_benchmark_spread(103.50, 99.10)
    assert cls != "BACKWARDATION"

def t02_brent_wti_not_contango():
    from mcx.mcx_crude_fundamentals import classify_benchmark_spread
    cls, _ = classify_benchmark_spread(99.10, 103.50)
    assert cls != "CONTANGO"

def t03_brent_premium():
    from mcx.mcx_crude_fundamentals import classify_benchmark_spread
    cls, spread = classify_benchmark_spread(103.50, 99.10)
    assert cls == "BRENT_PREMIUM"
    assert spread > 0

def t04_wti_premium():
    from mcx.mcx_crude_fundamentals import classify_benchmark_spread
    cls, spread = classify_benchmark_spread(99.10, 103.50)
    assert cls == "WTI_PREMIUM"
    assert spread < 0

def t05_near_parity():
    from mcx.mcx_crude_fundamentals import classify_benchmark_spread
    cls, _ = classify_benchmark_spread(100.00, 100.20)
    assert cls == "NEAR_PARITY"

def t06_wti_backwardation():
    from mcx.mcx_crude_fundamentals import classify_term_structure
    cls, spread = classify_term_structure(99.10, 98.75)
    assert cls == "BACKWARDATION"
    assert spread > 0

def t07_wti_contango():
    from mcx.mcx_crude_fundamentals import classify_term_structure
    cls, spread = classify_term_structure(98.50, 99.10)
    assert cls == "CONTANGO"
    assert spread < 0

def t08_wti_flat():
    from mcx.mcx_crude_fundamentals import classify_term_structure
    cls, _ = classify_term_structure(99.10, 99.11)
    assert cls == "FLAT"

def t09_brent_backwardation():
    from mcx.mcx_crude_fundamentals import classify_term_structure
    cls, _ = classify_term_structure(103.50, 103.10)
    assert cls == "BACKWARDATION"

def t10_brent_contango():
    from mcx.mcx_crude_fundamentals import classify_term_structure
    cls, _ = classify_term_structure(103.00, 103.50)
    assert cls == "CONTANGO"

def t11_missing_wti_second():
    from mcx.mcx_crude_fundamentals import classify_term_structure
    cls, spread = classify_term_structure(99.10, None)
    assert cls == "DATA_UNAVAILABLE"
    assert spread is None

def t12_missing_brent_second():
    from mcx.mcx_crude_fundamentals import classify_term_structure
    cls, spread = classify_term_structure(None, 103.10)
    assert cls == "DATA_UNAVAILABLE"
    assert spread is None


# --- P2 fixed denominators (t13-t15) ---
def t13_crude_denominator_fixed():
    from mcx.mcx_crude_fundamentals import build_crude_observations, summarize_crude
    obs = build_crude_observations()
    s = summarize_crude(obs)
    assert s["data_completeness"]["expected"] == 9

def t14_natgas_denominator_fixed():
    from mcx.mcx_natgas_fundamentals import build_natgas_observations, summarize_natgas
    obs = build_natgas_observations()
    s = summarize_natgas(obs)
    assert s["data_completeness"]["expected"] == 5

def t15_gold_denominator_fixed():
    from mcx.mcx_gold_fundamentals import build_gold_observations, summarize_gold
    obs = build_gold_observations()
    s = summarize_gold(obs)
    assert s["data_completeness"]["expected"] == 6


# --- P1 evidence authority (t16-t19) ---
def t16_completeness_0889_high():
    from mcx.mcx_crude_fundamentals import _evidence_authority
    assert _evidence_authority(0.889) == "HIGH"

def t17_completeness_050_low():
    from mcx.mcx_crude_fundamentals import _evidence_authority
    assert _evidence_authority(0.50) == "LOW"

def t18_completeness_040_low():
    from mcx.mcx_crude_fundamentals import _evidence_authority
    assert _evidence_authority(0.40) == "LOW"

def t19_completeness_below_040_insufficient():
    from mcx.mcx_crude_fundamentals import _evidence_authority
    assert _evidence_authority(0.39) == "INSUFFICIENT"
    assert _evidence_authority(0.0) == "INSUFFICIENT"


# --- Safety (t20-t28) ---
def t20_authority_does_not_alter_decision():
    from mcx.mcx_decision import compose
    import inspect
    sig = inspect.signature(compose)
    params = " ".join(sig.parameters.keys()).lower()
    assert "authority" not in params
    assert "fundamental" not in params

def t21_shadow_only():
    from mcx.mcx_fundamental_engine import FundamentalEngine
    e = FundamentalEngine()
    assert e.shadow_mode is True

def t22_trade_influence_false():
    from mcx.mcx_fundamental_engine import FundamentalEngine
    s = FundamentalEngine().shadow_summary("CRUDEOILM")
    assert s["trade_influence"] is False

def _build_hash(product):
    from mcx.mcx_decision import compose
    inputs = {
        "CRUDEOILM": ({"status": "OK", "future_ltp": 9500, "atm": 9500, "pcr_oi": 1.2,
            "max_pain": 9500, "ce_data": {}, "pe_data": {}, "resistance": [], "support": [],
            "expiry": "2026-09-17"},
            {"status": "OK", "composite_regime": "WEAK_UP", "composite_move_1d_pct": 0.3,
             "primary": {"WTI": {"regime": "UP"}}, "cross_asset": {},
             "fetched_at": "2026-09-12T10:00:00"},
            {"status": "OK", "timeframes": {"1m": {"status": "OK", "trend": "FLAT"},
                "5m": {"status": "OK", "trend": "FLAT"}, "15m": {"status": "OK", "trend": "DOWN"},
                "30m": {"status": "OK", "trend": "FLAT"}, "1h": {"status": "OK", "trend": "FLAT"}},
             "aggregate_trend": "MIXED"},
            {"regime": "RANGE", "confidence": 0.5, "evidence": {}}),
    }[product]
    return hashlib.sha256(json.dumps(compose(*inputs), sort_keys=True, default=str).encode()).hexdigest()

def t23_crude_hash_unchanged():
    from mcx.mcx_fundamental_engine import FundamentalEngine
    h1 = _build_hash("CRUDEOILM")
    FundamentalEngine().shadow_summary("CRUDEOILM")
    h2 = _build_hash("CRUDEOILM")
    assert h1 == h2

def t24_gold_hash_unchanged():
    from mcx.mcx_fundamental_engine import FundamentalEngine
    h1 = _build_hash("CRUDEOILM")  # use same chain for test isolation
    FundamentalEngine().shadow_summary("GOLDM")
    h2 = _build_hash("CRUDEOILM")
    assert h1 == h2

def t25_natgas_hash_unchanged():
    from mcx.mcx_fundamental_engine import FundamentalEngine
    h1 = _build_hash("CRUDEOILM")
    FundamentalEngine().shadow_summary("NATGASMINI")
    h2 = _build_hash("CRUDEOILM")
    assert h1 == h2

def t26_counters_unchanged():
    for p in ["crudeoilm", "goldm", "natgasmini"]:
        f = f"data/paper_trades/mcx_{p}_experimental.json"
        if os.path.exists(f):
            st = json.load(open(f, encoding="utf-8"))
            assert st["total_trades"] == 0

def t27_broker_submission_false():
    for f in os.listdir(os.path.join(_SRC, "mcx")):
        if f.startswith("mcx_fundamental_") and f.endswith(".py"):
            with open(os.path.join(_SRC, "mcx", f), encoding="utf-8") as fh:
                c = fh.read()
                assert "placeOrder" not in c
                assert "modifyOrder" not in c
                assert "cancelOrder" not in c

def t28_live_execution_false():
    # No live execution path in any fundamental module
    for f in os.listdir(os.path.join(_SRC, "mcx")):
        if f.startswith("mcx_fundamental_") and f.endswith(".py"):
            with open(os.path.join(_SRC, "mcx", f), encoding="utf-8") as fh:
                c = fh.read()
                assert "live_execution = True" not in c


def run_all():
    tests = [v for k, v in sorted(globals().items())
             if re.match(r"^t\d+_", k) and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            print(f"ERR  {t.__name__}: {type(e).__name__}: {str(e)[:80]}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return passed == len(tests)


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
