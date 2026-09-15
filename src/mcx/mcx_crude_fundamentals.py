"""CRUDEOILM fundamental engine — Section 5.4-5.11.
Shadow-only. No fabrication.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_fundamental_models import (
    make_observation, compute_freshness,
    REASON_SOURCE_UNAVAILABLE,
)
from mcx.mcx_fundamental_sources import (
    fetch_eia_petroleum, fetch_opec_decision,
    fetch_wti_brent_structure, fetch_china_crude_demand,
)


def classify_inventory_surprise(actual_change, consensus_change):
    """Section 5.5 — inventory surprise. Sign semantics preserved."""
    if consensus_change is None:
        return "CONSENSUS_UNAVAILABLE", None
    if actual_change is None:
        return "DATA_UNAVAILABLE", None
    try:
        surprise = float(actual_change) - float(consensus_change)
    except Exception:
        return "DATA_UNAVAILABLE", None
    if abs(surprise) < 0.25:
        return "INLINE", surprise
    if surprise < 0:
        # actual more negative than expected → draw > expected
        return "LARGER_DRAW", surprise
    return "LARGER_BUILD", surprise


def classify_supply_state(production_chg, refinery_util, cushing_chg, imports_chg=None):
    """Section 5.6 — supply state classification."""
    vals = [v for v in (production_chg, cushing_chg) if v is not None]
    if not vals:
        return "INSUFFICIENT_DATA"
    tightening = 0
    loosening = 0
    # Production up → loosening. Production down → tightening.
    if production_chg is not None:
        if production_chg > 0:
            loosening += 1
        elif production_chg < 0:
            tightening += 1
    # Cushing draw → tightening. Build → loosening.
    if cushing_chg is not None:
        if cushing_chg < 0:
            tightening += 1
        elif cushing_chg > 0:
            loosening += 1
    # Refinery util > 90 → strong demand
    refinery_state = "NEUTRAL"
    if refinery_util is not None:
        if refinery_util >= 92:
            refinery_state = "REFINERY_DEMAND_STRONG"
        elif refinery_util <= 85:
            refinery_state = "REFINERY_DEMAND_WEAK"
    if tightening > loosening:
        return "SUPPLY_TIGHTENING"
    if loosening > tightening:
        return "SUPPLY_LOOSENING"
    return "MIXED" if tightening == loosening and tightening > 0 else "INSUFFICIENT_DATA"


def classify_benchmark_spread(brent_front, wti_front, parity_threshold=0.50):
    """Section 5.7 (corrected): Brent-WTI is a CROSS-BENCHMARK spread.
    It does NOT determine BACKWARDATION/CONTANGO.
    """
    if brent_front is None or wti_front is None:
        return "DATA_UNAVAILABLE", None
    try:
        spread = round(float(brent_front) - float(wti_front), 4)
    except Exception:
        return "DATA_UNAVAILABLE", None
    if abs(spread) < parity_threshold:
        return "NEAR_PARITY", spread
    return ("BRENT_PREMIUM" if spread > 0 else "WTI_PREMIUM"), spread


def classify_term_structure(front, second, parity_threshold=0.05):
    """Section 5.7 (corrected): same-benchmark term structure.
    front > second  -> BACKWARDATION
    front < second  -> CONTANGO
    approximately equal -> FLAT
    """
    if front is None or second is None:
        return "DATA_UNAVAILABLE", None
    try:
        spread = round(float(front) - float(second), 4)
    except Exception:
        return "DATA_UNAVAILABLE", None
    if abs(spread) < parity_threshold:
        return "FLAT", spread
    return ("BACKWARDATION" if spread > 0 else "CONTANGO"), spread


def build_crude_observations(reference_week="2026-W36"):
    """Return dict: metric_id -> observation dict or {status: ...}."""
    obs = {}

    # EIA petroleum
    eia = fetch_eia_petroleum(reference_week)
    if eia.status == "FIXTURE_LOADED":
        for mid, m in (eia.payload.get("metrics") or {}).items():
            obs[mid] = make_observation(
                product="CRUDEOILM", driver_type="INVENTORY" if "STOCKS" in mid else "SUPPLY",
                metric_id=mid, reference_period=reference_week,
                observation_time_iso=eia.payload["release_time_utc"],
                units=m.get("units"), source="EIA",
                previous=m.get("previous"), consensus=m.get("consensus"),
                actual=m.get("actual"), freshness_policy="WEEKLY_EIA",
            )
    else:
        obs["EIA"] = {"status": REASON_SOURCE_UNAVAILABLE, "reason": eia.reason}

    # OPEC
    opec = fetch_opec_decision()
    if opec.status == "FIXTURE_LOADED":
        decisions = [e for e in opec.payload.get("events", [])
                     if e.get("event_type") == "OFFICIAL_DECISION"]
        if decisions:
            d = decisions[-1]
            obs["OPEC_LATEST_DECISION"] = make_observation(
                product="CRUDEOILM", driver_type="POLICY",
                metric_id="OPEC_LATEST_DECISION",
                reference_period=d["date"],
                observation_time_iso=d["publication_time_utc"],
                source="OPEC", freshness_policy="OPEC_POLICY",
                actual=d["decision"].get("cut_bpd"),
                source_identifier=d["decision"].get("source_url"),
            )
    else:
        obs["OPEC"] = {"status": REASON_SOURCE_UNAVAILABLE}

    # WTI/Brent — Section 5.7 corrected (cross-benchmark vs term structure)
    wb = fetch_wti_brent_structure()
    if wb.status == "FIXTURE_LOADED":
        p = wb.payload
        # 1) Benchmark spread (cross-commodity)
        bench_cls, bench_spread = classify_benchmark_spread(
            p.get("brent_front"), p.get("wti_front"))
        obs["BENCHMARK_SPREAD"] = make_observation(
            product="CRUDEOILM", driver_type="PRICE_STRUCTURE",
            metric_id="BENCHMARK_SPREAD",
            reference_period="2026-09-11",
            observation_time_iso=p["timestamp"],
            source="yfinance", freshness_policy="FAST_MARKET",
            actual=bench_spread, direction=bench_cls,
        )
        obs["BENCHMARK_SPREAD"]["classification"] = bench_cls
        # 2) WTI term structure (same benchmark, front vs second)
        wti_cls, wti_spread = classify_term_structure(
            p.get("wti_front"), p.get("wti_next"))
        obs["WTI_TERM_STRUCTURE"] = make_observation(
            product="CRUDEOILM", driver_type="PRICE_STRUCTURE",
            metric_id="WTI_TERM_STRUCTURE",
            reference_period="2026-09-11",
            observation_time_iso=p["timestamp"],
            source="yfinance", freshness_policy="FAST_MARKET",
            actual=wti_spread, direction=wti_cls,
        )
        obs["WTI_TERM_STRUCTURE"]["classification"] = wti_cls
        # 3) Brent term structure
        brent_cls, brent_spread = classify_term_structure(
            p.get("brent_front"), p.get("brent_next"))
        obs["BRENT_TERM_STRUCTURE"] = make_observation(
            product="CRUDEOILM", driver_type="PRICE_STRUCTURE",
            metric_id="BRENT_TERM_STRUCTURE",
            reference_period="2026-09-11",
            observation_time_iso=p["timestamp"],
            source="yfinance", freshness_policy="FAST_MARKET",
            actual=brent_spread, direction=brent_cls,
        )
        obs["BRENT_TERM_STRUCTURE"]["classification"] = brent_cls

    # China demand
    cn = fetch_china_crude_demand()
    obs["CHINA_DEMAND"] = {"status": REASON_SOURCE_UNAVAILABLE, "reason": cn.reason}

    return obs


def summarize_crude(observations):
    """Section 5.11 — deterministic shadow summary."""
    def _get(mid):
        o = observations.get(mid, {})
        return o if isinstance(o, dict) and "actual" in o else None

    crude_stocks = _get("COMMERCIAL_CRUDE_STOCKS")
    cushing = _get("CUSHING_CRUDE_STOCKS")
    gasoline = _get("GASOLINE_STOCKS")
    distillate = _get("DISTILLATE_STOCKS")
    refinery = _get("REFINERY_UTILIZATION")
    production = _get("US_CRUDE_PRODUCTION")

    flags = []
    if crude_stocks and crude_stocks.get("actual") is not None:
        chg = crude_stocks["actual"]
        flags.append("CRUDE_DRAW" if chg < 0 else "CRUDE_BUILD")
    if gasoline and gasoline.get("actual") is not None:
        chg = gasoline["actual"]
        flags.append("GAS_BUILD" if chg > 0 else "GAS_DRAW")
    if distillate and distillate.get("actual") is not None:
        chg = distillate["actual"]
        flags.append("DIST_BUILD" if chg > 0 else "DIST_DRAW")

    # Conflict detection — Section 5.5
    crude_dir = None
    if crude_stocks and crude_stocks.get("actual") is not None:
        crude_dir = "BULL" if crude_stocks["actual"] < 0 else "BEAR"
    gas_dir = None
    if gasoline and gasoline.get("actual") is not None:
        gas_dir = "BEAR" if gasoline["actual"] > 0 else "BULL"

    state = "INCONCLUSIVE"
    if crude_dir and gas_dir and crude_dir != gas_dir:
        state = "MIXED"
    elif crude_dir:
        state = "BULLISH" if crude_dir == "BULL" else "BEARISH"
    else:
        state = "DATA_UNAVAILABLE"

    # Completeness
    # Section 5 close-out P2: fixed denominator — must not change based on availability
    expected = [
        "COMMERCIAL_CRUDE_STOCKS", "CUSHING_CRUDE_STOCKS", "GASOLINE_STOCKS",
        "DISTILLATE_STOCKS", "REFINERY_UTILIZATION", "US_CRUDE_PRODUCTION",
        "BENCHMARK_SPREAD", "WTI_TERM_STRUCTURE", "OPEC_LATEST_DECISION",
    ]  # exactly 9 documented components
    available = sum(1 for m in expected if _get(m) is not None)
    return {
        "product": "CRUDEOILM",
        "driver_flags": flags,
        "crude_direction": crude_dir,
        "gasoline_direction": gas_dir,
        "fundamental_state": state,
        "raw_fundamental_state": state,
        "data_completeness": {"expected": len(expected), "available": available,
                             "ratio": round(available / len(expected), 3)},
        "evidence_authority": _evidence_authority(round(available / len(expected), 3)),
        "shadow_only": True,
        "trade_influence": False,
    }


def _evidence_authority(ratio):
    """Section 5 close-out P1: data-completeness category.
    NOT trade confidence, NOT win probability, NOT strategy score.
    """
    if ratio >= 0.80:
        return "HIGH"
    if ratio >= 0.60:
        return "MODERATE"
    if ratio >= 0.40:
        return "LOW"
    return "INSUFFICIENT"



if __name__ == "__main__":
    obs = build_crude_observations()
    s = summarize_crude(obs)
    print(f"CRUDE observations: {len(obs)}")
    print(f"State: {s['fundamental_state']}")
    print(f"Completeness: {s['data_completeness']}")
    # Test surprise logic
    print("Surprise tests:")
    for a, c in [(-5.0, -1.0), (-1.0, -5.0), (3.0, 3.1), (None, -1.0), (-2.0, None)]:
        print(f"  actual={a} consensus={c} → {classify_inventory_surprise(a, c)}")
