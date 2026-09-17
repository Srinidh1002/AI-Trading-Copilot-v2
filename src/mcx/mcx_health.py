"""MCX startup health checks — verify all components load.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def check():
    results = []
    modules = [
        ("contracts", "mcx.mcx_contracts", "PRODUCTS"),
        ("fyers_identity", "mcx.mcx_fyers_bridge_v2", "MCXFyersIdentityResolverV2"),
        ("fyers_chain", "mcx.mcx_fyers_native_chain_v2", "MCXFyersNativeChainV2"),
        ("fyers_runtime", "mcx.mcx_fyers_runtime_v2", "MCXFyersRuntimeV2"),
        ("mtf", "mcx.mcx_mtf", "compute_mtf"),
        ("regime", "mcx.mcx_regime", "classify"),
        ("decision", "mcx.mcx_decision", "compose"),
        ("pcr", "mcx.mcx_pcr", "StablePCR"),
        ("strike", "mcx.mcx_strike", "select_strike"),
        ("capital", "mcx.mcx_capital", "compute_paper_fill"),
        ("costs", "mcx.mcx_costs", "net_pnl"),
        ("data_quality", "mcx.mcx_data_quality", "evaluate_all"),
        ("calendar", "mcx.mcx_calendar", "get_session"),
        ("version", "mcx.mcx_version", "verify_all_epochs"),
        ("structure", "mcx.mcx_structure", "compute_structure"),
        ("price_oi", "mcx.mcx_price_oi", "PriceOITracker"),
        ("setup", "mcx.mcx_setup", "classify"),
        ("greeks", "mcx.mcx_greeks", "analyze_option"),
        ("position_manager", "mcx.mcx_position_manager", "evaluate_exit"),
        ("reconcile", "mcx.mcx_reconcile", "reconcile"),
        ("certification", "mcx.mcx_certification", "status"),
        ("holidays", "mcx.mcx_holidays", "MCX_HOLIDAYS_2026"),
        ("event_risk", "mcx.mcx_event_risk", "get_state"),
        ("learning", "mcx.mcx_learning", "collect"),
        ("scheduler", "mcx.mcx_scheduler", "status"),
        ("presession", "mcx.mcx_presession", "build_report"),
    ]
    for name, mod, attr in modules:
        try:
            m = __import__(mod, fromlist=[attr])
            getattr(m, attr)
            results.append((name, True, "OK"))
        except Exception as e:
            results.append((name, False, str(e)[:60]))
    return results


def print_health():
    r = check()
    print("=" * 70)
    print("MCX MODULE HEALTH CHECK")
    print("=" * 70)
    ok = True
    for name, status, detail in r:
        mark = "OK  " if status else "FAIL"
        print(f"  {mark}  {name:<20} {detail}")
        ok = ok and status
    print("=" * 70)
    print(f"ALL {len(r)} MODULES: {'HEALTHY' if ok else 'SOME FAILED'}")
    print("=" * 70)
    return ok


def product_readiness():
    """Report per-product readiness: contract, state, ledgers, runner, status."""
    import os
    out = {}
    for product in ("CRUDEOILM", "GOLDM", "SILVERM"):
        try:
            from mcx.mcx_version import get_product_epochs
            cfg = get_product_epochs(product) or {}
        except Exception:
            cfg = {}
        state_p = f"data/paper_trades/mcx_{product.lower()}_experimental.json"
        preds_p = f"data/paper_trades/mcx_{product.lower()}_predictions.jsonl"
        outs_p = f"data/paper_trades/mcx_{product.lower()}_outcomes.jsonl"
        decs_p = f"data/paper_trades/mcx_{product.lower()}_decisions.jsonl"
        has_state = os.path.exists(state_p)
        has_ledgers = os.path.exists(preds_p) or os.path.exists(outs_p) or os.path.exists(decs_p)
        epoch = cfg.get("epoch")
        eligible = cfg.get("certification_eligible", False)
        if product == "CRUDEOILM":
            status = "OPERATIONAL" if (has_state and eligible) else "PARTIAL"
        else:
            status = "PRECERT" if has_state else "NOT_INITIALIZED"
        out[product] = {
            "contract": "PRESENT_PROVISIONAL" if not eligible else "PRESENT",
            "state": "PRESENT" if has_state else "MISSING",
            "ledgers": "PRESENT" if has_ledgers else "MISSING",
            "runner": "SHARED_ARGV",
            "epoch": epoch,
            "certification_eligible": eligible,
            "status": status,
        }
    return out


def print_product_readiness():
    r = product_readiness()
    print()
    print("=" * 70)
    print("PRODUCT READINESS")
    print("=" * 70)
    for product, info in r.items():
        print(f"\n{product}")
        print(f"  contract              {info['contract']}")
        print(f"  state                 {info['state']}")
        print(f"  ledgers               {info['ledgers']}")
        print(f"  runner                {info['runner']}")
        print(f"  epoch                 {info['epoch']}")
        print(f"  cert_eligible         {info['certification_eligible']}")
        print(f"  status                {info['status']}")
    print("=" * 70)


def macro_health():
    """Section 4.37 — MACRO EVENT INTELLIGENCE health."""
    checks = {}
    try:
        from mcx.mcx_macro_models import SUPPORTED_EVENT_TYPES
        checks["event_model"] = "PASS" if len(SUPPORTED_EVENT_TYPES) >= 15 else "FAILED"
    except Exception:
        checks["event_model"] = "FAILED"
    try:
        from mcx.mcx_macro_sources import SOURCE_MATRIX, fetch_bls_cpi
        r = fetch_bls_cpi("2026-08")
        checks["official_sources"] = "PARTIAL" if r.status == "FIXTURE_LOADED" else "UNAVAILABLE"
    except Exception:
        checks["official_sources"] = "FAILED"
    try:
        from mcx.mcx_macro_calendar import MacroCalendar
        c = MacroCalendar()
        checks["calendar"] = "PASS" if len(c.all_events()) >= 5 else "PARTIAL"
    except Exception:
        checks["calendar"] = "FAILED"
    try:
        from mcx.mcx_macro_models import make_event
        e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
        checks["timezone"] = "PASS" if "+05:30" in e["scheduled_time_ist"] else "FAILED"
    except Exception:
        checks["timezone"] = "FAILED"
    try:
        from mcx.mcx_macro_surprise import classify_surprise
        checks["surprise_engine"] = "PASS"
    except Exception:
        checks["surprise_engine"] = "FAILED"
    try:
        from mcx.mcx_macro_reaction import classify_reaction
        checks["reaction_engine"] = "PASS"
    except Exception:
        checks["reaction_engine"] = "FAILED"
    try:
        from mcx.mcx_macro_store import save_event
        checks["event_store"] = "PASS"
    except Exception:
        checks["event_store"] = "FAILED"
    checks["consensus_provider"] = "UNCONFIGURED"
    return checks


def print_macro_health():
    r = macro_health()
    print()
    print("=" * 70)
    print("MACRO EVENT INTELLIGENCE")
    print("=" * 70)
    for k, v in r.items():
        print(f"  {k:20} {v}")
    print("=" * 70)


def fundamental_health():
    """Section 5.34 — COMMODITY FUNDAMENTALS health."""
    checks = {}
    try:
        from mcx.mcx_crude_fundamentals import build_crude_observations
        obs = build_crude_observations()
        eia = any(k.startswith("COMMERCIAL") for k in obs)
        checks["crude_eia"] = "PASS" if eia else "UNAVAILABLE"
    except Exception:
        checks["crude_eia"] = "FAILED"
    try:
        from mcx.mcx_crude_fundamentals import build_crude_observations
        obs = build_crude_observations()
        checks["crude_opec"] = "PASS" if "OPEC_LATEST_DECISION" in obs else "PARTIAL"
        # Section 5 close-out P0: metric split into BENCHMARK_SPREAD + WTI_TERM_STRUCTURE
        has_struct = ("BENCHMARK_SPREAD" in obs) and ("WTI_TERM_STRUCTURE" in obs)
        checks["crude_market_structure"] = "PASS" if has_struct else "UNAVAILABLE"
    except Exception:
        checks["crude_opec"] = "FAILED"
    try:
        from mcx.mcx_natgas_fundamentals import build_natgas_observations
        obs = build_natgas_observations()
        checks["natgas_storage"] = "PASS" if "NATGAS_STORAGE" in obs else "UNAVAILABLE"
        checks["natgas_weather"] = "PASS" if "WEATHER_DEMAND" in obs else "UNAVAILABLE"
        checks["natgas_lng"] = "UNAVAILABLE"
    except Exception:
        checks["natgas_storage"] = "FAILED"
    try:
        from mcx.mcx_gold_fundamentals import build_gold_observations
        obs = build_gold_observations()
        checks["gold_real_yields"] = "PASS" if "REAL_YIELDS" in obs else "UNAVAILABLE"
        checks["gold_etf"] = "UNAVAILABLE"
        checks["gold_central_banks"] = "UNAVAILABLE"
    except Exception:
        checks["gold_real_yields"] = "FAILED"
    return checks


def print_fundamental_health():
    r = fundamental_health()
    print()
    print("=" * 70)
    print("COMMODITY FUNDAMENTALS")
    print("=" * 70)
    for k, v in r.items():
        print(f"  {k:26} {v}")
    print("=" * 70)


def breaking_health():
    """Section 6.43 — BREAKING NEWS INTELLIGENCE."""
    checks = {}
    try:
        from mcx.mcx_breaking_models import EVENT_TYPES, SOURCE_TIERS, VERIFICATION_STATES
        checks["event_model"] = "PASS" if len(EVENT_TYPES) >= 25 and len(SOURCE_TIERS) == 5 else "FAILED"
    except Exception:
        checks["event_model"] = "FAILED"
    try:
        from mcx.mcx_breaking_sources import SOURCE_REGISTRY, fetch_live_news
        checks["source_registry"] = "PARTIAL" if len(SOURCE_REGISTRY) >= 5 else "UNCONFIGURED"
    except Exception:
        checks["source_registry"] = "FAILED"
    try:
        from mcx.mcx_breaking_verify import compute_verification
        checks["verification_engine"] = "PASS"
    except Exception:
        checks["verification_engine"] = "FAILED"
    try:
        from mcx.mcx_breaking_dedup import classify_against_existing
        checks["dedup_engine"] = "PASS"
    except Exception:
        checks["dedup_engine"] = "FAILED"
    try:
        from mcx.mcx_breaking_engine import EVENT_RELEVANCE
        checks["cluster_engine"] = "PASS" if len(EVENT_RELEVANCE) >= 10 else "PARTIAL"
    except Exception:
        checks["cluster_engine"] = "FAILED"
    try:
        from mcx.mcx_breaking_reaction import classify_observed_reaction
        checks["reaction_engine"] = "PASS"
    except Exception:
        checks["reaction_engine"] = "FAILED"
    try:
        from mcx.mcx_breaking_store import save_event_version
        checks["event_store"] = "PASS"
    except Exception:
        checks["event_store"] = "FAILED"
    checks["live_news_provider"] = "UNCONFIGURED"
    return checks


def print_breaking_health():
    r = breaking_health()
    print()
    print("=" * 70)
    print("BREAKING NEWS INTELLIGENCE")
    print("=" * 70)
    for k, v in r.items():
        print(f"  {k:22} {v}")
    print("=" * 70)


def execution_health():
    """Section 7 — PAPER execution integrity."""
    checks = {}
    try:
        # S7_STAGE_6_HEALTH — per-product calibration reporting
        from mcx.mcx_exec_quote import (EXECUTION_QUOTE_MAX_AGE_SECONDS,
                                        EXECUTION_FRESHNESS_CALIBRATED)
        if EXECUTION_FRESHNESS_CALIBRATED and EXECUTION_QUOTE_MAX_AGE_SECONDS and EXECUTION_QUOTE_MAX_AGE_SECONDS > 0:
            checks["quote_model"] = "PASS"
        else:
            checks["quote_model"] = "UNCALIBRATED"
        checks["freshness_config"] = EXECUTION_QUOTE_MAX_AGE_SECONDS
        checks["freshness_calibrated"] = EXECUTION_FRESHNESS_CALIBRATED
        try:
            from mcx.mcx_exec_config import (is_freshness_calibrated,
                                             get_execution_quote_max_age_seconds,
                                             is_quantity_semantics_verified)
            for p in ("CRUDEOILM", "GOLDM", "SILVERM"):
                checks[f"freshness_{p}"] = (
                    "PASS" if is_freshness_calibrated(p) else "UNCALIBRATED")
                checks[f"max_age_{p}_s"] = get_execution_quote_max_age_seconds(p)
                checks[f"qty_semantics_{p}"] = (
                    "PASS" if is_quantity_semantics_verified(p) else "UNVERIFIED")
        except Exception as _e:
            checks["per_product_calibration"] = f"ERR: {_e}"
    except Exception:
        checks["quote_model"] = "FAILED"
    try:
        from mcx.mcx_exec_depth import extract_depth
        checks["depth_parser"] = "PASS"
    except Exception:
        checks["depth_parser"] = "FAILED"
    try:
        from mcx.mcx_exec_fill import compute_paper_fill_v2
        checks["fill_engine"] = "PASS"
    except Exception:
        checks["fill_engine"] = "FAILED"
    try:
        from mcx.mcx_exec_countability import is_countable
        checks["countability_gate"] = "PASS"
    except Exception:
        checks["countability_gate"] = "FAILED"
    try:
        from mcx.mcx_exec_first_touch import FirstTouchTracker
        checks["first_touch_tracker"] = "PASS"
    except Exception:
        checks["first_touch_tracker"] = "FAILED"
    try:
        from mcx.mcx_exec_lifecycle import LIFECYCLE_STATES
        checks["lifecycle_states"] = "PASS" if len(LIFECYCLE_STATES) >= 14 else "PARTIAL"
    except Exception:
        checks["lifecycle_states"] = "FAILED"
    try:
        from mcx.mcx_exec_recovery import check_open_position
        checks["recovery_engine"] = "PASS"
    except Exception:
        checks["recovery_engine"] = "FAILED"
    try:
        from mcx.mcx_exec_recorder import record_quote
        checks["evidence_recorder"] = "PASS"
    except Exception:
        checks["evidence_recorder"] = "FAILED"
    # M6_live_depth_from_config - report per-product execution depth status
    try:
        import json as _json, os as _os
        _cfg_path = "data/execution_evidence/mcx/exec_config.json"
        _cfg = {}
        if _os.path.exists(_cfg_path):
            with open(_cfg_path, encoding="utf-8") as _f:
                _cfg = _json.load(_f)

        try:
            from mcx.mcx_version import is_certification_eligible as _cert_elig
        except Exception:
            _cert_elig = lambda p: False

        for _p in ("CRUDEOILM", "GOLDM", "SILVERM"):
            _pc = _cfg.get(_p, {}) or {}
            _depth_ok = bool(_pc.get("rest_depth_supported"))
            _qty_ok = bool(_pc.get("depth_quantity_semantics_verified"))
            _fresh_ok = bool(_pc.get("execution_freshness_calibrated"))
            _full_exec = _depth_ok and _qty_ok and _fresh_ok

            if _full_exec and _cert_elig(_p):
                _status = "PASS"
            elif _full_exec and not _cert_elig(_p):
                _status = "PASS_EXECUTION_PRECERT"
            elif not _cfg:
                _status = "PENDING_LIVE_PROBE"
            else:
                _status = "FAILED"
            checks[f"live_depth_verified_{_p}"] = _status

        # Aggregate: for backward compatibility, one combined key
        _all = [checks.get(f"live_depth_verified_{_p}") for _p in ("CRUDEOILM", "GOLDM", "SILVERM")]
        if all(_s == "PASS" for _s in _all):
            checks["live_depth_verified"] = "PASS"
        elif all(_s in ("PASS", "PASS_EXECUTION_PRECERT") for _s in _all):
            checks["live_depth_verified"] = "PASS_EXECUTION_PRECERT"
        else:
            checks["live_depth_verified"] = "PENDING_LIVE_PROBE"
    except Exception as _e:
        checks["live_depth_verified"] = f"ERROR: {str(_e)[:40]}"

    return checks


def print_execution_health():
    r = execution_health()
    print()
    print("=" * 70)
    print("PAPER EXECUTION INTEGRITY (Section 7)")
    print("=" * 70)
    for k, v in r.items():
        print(f"  {k:22} {v}")
    print("=" * 70)


if __name__ == "__main__":
    print_health()
    print_macro_health()
    print_fundamental_health()
    print_breaking_health()
    print_execution_health()
    print_product_readiness()
