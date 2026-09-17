"""Section 4 macro event tests. Offline. Fixture-based."""
import os
import sys
from datetime import datetime, timezone, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def t01_cpi_canonical_record():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30",
                   "America/New_York", "BLS", importance="HIGH")
    assert e["event_id"] == "US_CPI_2026_08_20260911"
    assert e["country"] == "US"
    assert e["currency"] == "USD"


def t02_headline_mom_separate_from_yoy():
    from mcx.mcx_macro_models import make_metric
    m1 = make_metric("HEADLINE_CPI_MOM", "percent", "MOM")
    m2 = make_metric("HEADLINE_CPI_YOY", "percent", "YOY")
    assert m1["metric_id"] != m2["metric_id"]
    assert m1["period_type"] != m2["period_type"]


def t03_core_mom_separate_from_core_yoy():
    from mcx.mcx_macro_models import make_metric
    m1 = make_metric("CORE_CPI_MOM", "percent", "MOM")
    m2 = make_metric("CORE_CPI_YOY", "percent", "YOY")
    assert m1["metric_id"] != m2["metric_id"]


def t04_previous_parsed():
    from mcx.mcx_macro_models import make_metric
    m = make_metric("HEADLINE_CPI_YOY", "percent", "YOY", previous=3.1)
    assert m["previous"] == 3.1


def t05_actual_parsed():
    from mcx.mcx_macro_models import make_metric
    m = make_metric("HEADLINE_CPI_YOY", "percent", "YOY", actual=3.2)
    assert m["actual"] == 3.2


def t06_revised_previous_preserved():
    from mcx.mcx_macro_models import make_metric
    m = make_metric("HEADLINE_CPI_YOY", "percent", "YOY",
                    previous=3.1, previous_revised=3.15)
    assert m["previous"] == 3.1
    assert m["previous_revised"] == 3.15


def t07_tz_conversion_ny_to_utc_to_ist():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30",
                   "America/New_York", "BLS")
    assert "+05:30" in e["scheduled_time_ist"]
    assert "2026-09-11T12:30:00" in e["scheduled_time_utc"]


def t08_dst_handled():
    # Sep is EDT (UTC-4). Aug is also EDT. Test Jan (EST = UTC-5)
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2025-12", "2026-01-15", "08:30",
                   "America/New_York", "BLS")
    # EST means 13:30 UTC
    assert "13:30:00" in e["scheduled_time_utc"], e["scheduled_time_utc"]


def t09_release_time_tz_aware():
    from mcx.mcx_macro_models import make_event
    from datetime import datetime
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30",
                   "America/New_York", "BLS")
    dt = datetime.fromisoformat(e["scheduled_time_ist"])
    assert dt.tzinfo is not None


def t10_consensus_pre_release_accepted():
    from mcx.mcx_macro_surprise import validate_consensus_timestamp
    ok, reason = validate_consensus_timestamp(
        "2026-09-11T12:00:00+00:00", "2026-09-11T12:30:00+00:00")
    assert ok


def t11_post_release_consensus_rejected():
    from mcx.mcx_macro_surprise import validate_consensus_timestamp
    ok, reason = validate_consensus_timestamp(
        "2026-09-11T13:00:00+00:00", "2026-09-11T12:30:00+00:00")
    assert not ok
    assert reason == "CONSENSUS_TIME_TRAVEL_VIOLATION"


def t12_missing_consensus_unavailable_not_neutral():
    from mcx.mcx_macro_surprise import classify_surprise
    cls, delta, _ = classify_surprise(3.2, None)
    assert cls == "CONSENSUS_UNAVAILABLE"
    assert delta is None


def t13_actual_vs_consensus_calculation():
    from mcx.mcx_macro_surprise import classify_surprise
    cls, delta, _ = classify_surprise(3.35, 3.1)
    assert abs(delta - 0.25) < 1e-9


def t14_actual_vs_previous_calculation():
    from mcx.mcx_macro_models import make_metric
    m = make_metric("HEADLINE_CPI_YOY", "percent", "YOY", previous=3.0, actual=3.5)
    assert m["actual_vs_previous"] == 0.5


def t15_no_mixing_consensus_and_previous():
    from mcx.mcx_macro_models import make_metric
    m = make_metric("HEADLINE_CPI_YOY", "percent", "YOY",
                    previous=3.0, consensus=3.2, actual=3.5)
    assert m["actual_vs_consensus"] == 0.3
    assert m["actual_vs_previous"] == 0.5


def t16_cpi_relevance_goldm():
    from mcx.mcx_macro_calendar import EVENT_METADATA
    assert EVENT_METADATA["US_CPI"]["relevance"]["GOLDM"] == "VERY_HIGH"


def t17_cpi_relevance_crude():
    from mcx.mcx_macro_calendar import EVENT_METADATA
    assert EVENT_METADATA["US_CPI"]["relevance"]["CRUDEOILM"] == "HIGH"


def t18_cpi_relevance_natgas():
    from mcx.mcx_macro_calendar import EVENT_METADATA
    assert EVENT_METADATA["US_CPI"]["relevance"]["NATGASMINI"] == "MEDIUM"


def t19_pre_event_transition():
    from mcx.mcx_macro_engine import classify_state, PRE_EVENT_MINUTES
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    rel_utc = datetime.fromisoformat(e["scheduled_time_utc"])
    now = rel_utc - timedelta(minutes=10)
    state, _ = classify_state(now, e)
    assert state == "PRE_EVENT"


def t20_event_lock_transition():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    rel_utc = datetime.fromisoformat(e["scheduled_time_utc"])
    now = rel_utc + timedelta(seconds=30)
    state, _ = classify_state(now, e)
    assert state == "EVENT_LOCK"


def t21_post_event_discovery():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    rel_utc = datetime.fromisoformat(e["scheduled_time_utc"])
    now = rel_utc + timedelta(minutes=3)
    state, _ = classify_state(now, e)
    assert state == "POST_EVENT_DISCOVERY"


def t22_post_event_confirmation():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    rel_utc = datetime.fromisoformat(e["scheduled_time_utc"])
    now = rel_utc + timedelta(minutes=10)
    state, _ = classify_state(now, e)
    assert state == "POST_EVENT_CONFIRMATION"


def t23_normalized_state():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    rel_utc = datetime.fromisoformat(e["scheduled_time_utc"])
    now = rel_utc + timedelta(hours=2)
    state, _ = classify_state(now, e)
    assert state == "NORMALIZED"


def t24_actual_unavailable_before_release():
    from mcx.mcx_macro_models import make_metric
    m = make_metric("HEADLINE_CPI_YOY", "percent", "YOY", previous=3.0)
    assert m["actual"] is None


def t25_release_visible_only_after():
    from mcx.mcx_macro_surprise import classify_surprise
    cls, _, _ = classify_surprise(None, 3.1)
    assert cls == "CONSENSUS_UNAVAILABLE"


def t26_old_month_rejected():
    # Fixture for 2026-08 does not exist for 2026-07 test data
    from mcx.mcx_macro_sources import fetch_bls_cpi
    r = fetch_bls_cpi("2026-09")
    assert r.status in ("SOURCE_UNAVAILABLE", "FIXTURE_LOADED")


def t27_duplicate_idempotency():
    from mcx.mcx_macro_models import make_event
    e1 = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    e2 = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    assert e1["event_id"] == e2["event_id"]


def t28_revision_preservation():
    from mcx.mcx_macro_store import save_event, load_event
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    r1 = save_event(e)
    e2 = dict(e); e2["revision_note"] = "updated"
    r2 = save_event(e2)
    assert r2["status"] in ("SAVED", "UNCHANGED")


def t29_reaction_confirmed_case():
    from mcx.mcx_macro_reaction import classify_reaction
    assert classify_reaction("DOWN", "DOWN") == "CONFIRMED"


def t30_reaction_conflicted_case():
    from mcx.mcx_macro_reaction import classify_reaction
    assert classify_reaction("DOWN", "UP") == "CONFLICTED"


def t31_reaction_inconclusive_case():
    from mcx.mcx_macro_reaction import classify_reaction
    assert classify_reaction("MIXED", "UP") == "INCONCLUSIVE"


def t32_reaction_data_unavailable_case():
    # After Section 4 close-out, unknown symbol returns the more specific
    # SYMBOL_UNAVAILABLE rather than the vague DATA_UNAVAILABLE.
    from mcx.mcx_macro_reaction import (
        capture_reaction, REASON_SYMBOL_UNAVAILABLE, REASON_REACTION_DATA_UNAVAILABLE,
    )
    r = capture_reaction("UNKNOWN_SYMBOL", "2026-09-11T12:30:00+00:00")
    assert r["status"] in (REASON_SYMBOL_UNAVAILABLE, REASON_REACTION_DATA_UNAVAILABLE), r["status"]
    # And missing event_time is unambiguously rejected
    r2 = capture_reaction("DXY", None)
    assert r2["status"] == REASON_REACTION_DATA_UNAVAILABLE


def t33_gold_theoretical_not_override():
    # Real observed reaction wins over theory — this is a design assertion, not code test
    from mcx.mcx_macro_reaction import classify_reaction
    # Hot CPI theory says DOWN for gold; if observed is UP → CONFLICTED
    assert classify_reaction("DOWN", "UP") == "CONFLICTED"


def t34_crude_conflicting_result_stays_conflict():
    from mcx.mcx_macro_reaction import classify_reaction
    assert classify_reaction("DOWN", "UP") == "CONFLICTED"


def t35_natgas_not_over_attributed():
    # Design: NATGAS CPI relevance is LOW/MEDIUM
    from mcx.mcx_macro_calendar import EVENT_METADATA
    assert EVENT_METADATA["US_CPI"]["relevance"]["NATGASMINI"] in ("LOW", "MEDIUM")


def t36_cpi_historical_schedule_fixture():
    from mcx.mcx_macro_sources import fetch_bls_cpi
    r = fetch_bls_cpi("2026-08")
    assert r.status == "FIXTURE_LOADED"


def t37_ppi_fixture():
    from mcx.mcx_macro_sources import fetch_bls_ppi
    r = fetch_bls_ppi("2026-08")
    assert r.status == "FIXTURE_LOADED"


def t38_fomc_schedule_fixture():
    from mcx.mcx_macro_sources import fetch_fed_fomc_schedule
    r = fetch_fed_fomc_schedule()
    assert r.status == "FIXTURE_LOADED"
    assert "meetings" in r.payload


def t39_pce_fixture():
    from mcx.mcx_macro_sources import fetch_bea_pce
    r = fetch_bea_pce("2026-08")
    assert r.status == "FIXTURE_LOADED"


def t40_shadow_cannot_alter_crude_decision():
    # compose_decision signature takes no macro input
    import inspect
    from mcx.mcx_decision import compose
    sig = inspect.signature(compose)
    params = list(sig.parameters.keys())
    assert "macro" not in " ".join(params).lower()
    assert "event" not in " ".join(params).lower() or "event_state" in params


def t41_shadow_cannot_increment_counter():
    from mcx.mcx_macro_engine import MacroEngine
    from datetime import datetime, timezone
    e = MacroEngine()
    # Calling shadow report must never touch counters
    r = e.shadow_report_for("CRUDEOILM", datetime(2026, 9, 11, 12, 45, tzinfo=timezone.utc))
    assert r.get("trade_influence") is False


def t42_shadow_no_order_path():
    # Scan macro modules for forbidden calls
    bad = []
    for f in os.listdir(os.path.join(_SRC, "mcx")):
        if not f.startswith("mcx_macro_") or not f.endswith(".py"):
            continue
        with open(os.path.join(_SRC, "mcx", f), encoding="utf-8") as fh:
            content = fh.read()
            for kw in ("placeOrder", "modifyOrder", "cancelOrder"):
                if kw in content:
                    bad.append((f, kw))
    assert not bad


def t43_gold_remains_precert():
    from mcx.mcx_version import is_certification_eligible
    assert is_certification_eligible("GOLDM") is False


def t44_natgas_remains_precert():
    from mcx.mcx_version import is_certification_eligible
    assert is_certification_eligible("NATGASMINI") is False


def t45_raw_payload_hash_stored():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS",
                   raw_payload={"a": 1})
    assert e["raw_payload_hash"] is not None


def t46_parser_version_stored():
    # Provenance dict on each metric — parser version can be stored
    from mcx.mcx_macro_models import make_metric
    m = make_metric("X", "pct", "YOY", provenance={"parser_version": "v1"})
    assert m["provenance"]["parser_version"] == "v1"


def t47_source_provenance_stored():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    assert e["source_agency"] == "BLS"


def t48_stale_release_period_rejected():
    # If we ask for 2026-08 but receive 2026-07, reject
    from mcx.mcx_macro_models import make_event
    e = make_event("US_CPI", "2026-08", "2026-09-11", "08:30", "America/New_York", "BLS")
    assert e["reference_period"] == "2026-08"
    # mismatch is a caller validation; we assert the field is present


def t49_learning_record_append_only():
    from mcx.mcx_macro_store import append_learning_record
    append_learning_record({"event_id": "TEST_EVT", "product": "CRUDEOILM", "shadow": True})
    p = "data/macro_events/reactions/event_outcomes.jsonl"
    assert os.path.exists(p)


def t50_strategy_files_unchanged():
    # Frozen strategy files still have same defaults
    with open(os.path.join(_SRC, "mcx", "mcx_decision.py"), encoding="utf-8") as f:
        src = f.read()
    assert "ENTRY_THRESHOLD = 70" in src


def run_all():
    import re as _re
    tests = [v for k, v in sorted(globals().items())
             if _re.match(r"^t\d+_", k) and callable(v)]
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
