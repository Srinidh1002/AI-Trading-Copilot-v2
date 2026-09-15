"""Section 4 close-out tests — FOMC TZ + historical reaction semantics."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")


def t01_fomc_statement_ny_to_utc():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09", "2026-09-16", "14:00",
                   "America/New_York", "Federal Reserve")
    assert e["scheduled_time_utc"] == "2026-09-16T18:00:00+00:00", e["scheduled_time_utc"]


def t02_fomc_statement_ny_to_ist():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09", "2026-09-16", "14:00",
                   "America/New_York", "Federal Reserve")
    assert e["scheduled_time_ist"] == "2026-09-16T23:30:00+05:30", e["scheduled_time_ist"]


def t03_press_conf_ny_to_utc():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09_pc", "2026-09-16", "14:30",
                   "America/New_York", "Federal Reserve")
    assert e["scheduled_time_utc"] == "2026-09-16T18:30:00+00:00", e["scheduled_time_utc"]


def t04_press_conf_ny_to_ist_rollover():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09_pc", "2026-09-16", "14:30",
                   "America/New_York", "Federal Reserve")
    assert e["scheduled_time_ist"] == "2026-09-17T00:00:00+05:30", e["scheduled_time_ist"]


def t05_statement_and_press_conf_separate():
    from mcx.mcx_macro_models import make_event
    e1 = make_event("US_FOMC_STATEMENT", "2026-09", "2026-09-16", "14:00",
                    "America/New_York", "Federal Reserve")
    e2 = make_event("US_FOMC_RATE", "2026-09", "2026-09-16", "14:30",
                    "America/New_York", "Federal Reserve")
    assert e1["event_id"] != e2["event_id"]
    assert e1["scheduled_time_ist"] != e2["scheduled_time_ist"]


def t06_press_conf_date_rollover_preserved():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09_pc", "2026-09-16", "14:30",
                   "America/New_York", "Federal Reserve")
    src_date = e["scheduled_time_src_iso"][:10]
    ist_date = e["scheduled_time_ist"][:10]
    assert src_date == "2026-09-16"
    assert ist_date == "2026-09-17"


def t07_event_state_before_statement_release():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09", "2026-09-16", "14:00",
                   "America/New_York", "Federal Reserve")
    # At 2026-09-16 23:20 IST (10 min before release)
    now_ist = datetime(2026, 9, 16, 23, 20, tzinfo=IST)
    state, _ = classify_state(now_ist, e)
    assert state == "PRE_EVENT", f"got {state}"


def t08_event_state_at_statement_release():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09", "2026-09-16", "14:00",
                   "America/New_York", "Federal Reserve")
    # At 2026-09-16 23:30 IST (release moment)
    now_ist = datetime(2026, 9, 16, 23, 30, 0, tzinfo=IST)
    state, _ = classify_state(now_ist, e)
    assert state == "EVENT_LOCK", f"got {state}"


def t09_no_press_conf_result_before_release():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09_pc", "2026-09-16", "14:30",
                   "America/New_York", "Federal Reserve")
    # At 2026-09-16 23:55 IST (before 00:00 IST release)
    now_ist = datetime(2026, 9, 16, 23, 55, tzinfo=IST)
    state, _ = classify_state(now_ist, e)
    assert state == "PRE_EVENT", f"got {state}"


def t10_press_conf_released_after_00_ist():
    from mcx.mcx_macro_engine import classify_state
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-09_pc", "2026-09-16", "14:30",
                   "America/New_York", "Federal Reserve")
    # At 2026-09-17 00:00:30 IST
    now_ist = datetime(2026, 9, 17, 0, 0, 30, tzinfo=IST)
    state, _ = classify_state(now_ist, e)
    assert state == "EVENT_LOCK", f"got {state}"


def t11_dst_aware_ny_jan():
    from mcx.mcx_macro_models import make_event
    e = make_event("US_FOMC_STATEMENT", "2026-01", "2026-01-28", "14:00",
                   "America/New_York", "Federal Reserve")
    # EST = UTC-5 → 14:00 EST = 19:00 UTC
    assert e["scheduled_time_utc"] == "2026-01-28T19:00:00+00:00", e["scheduled_time_utc"]


def t12_historical_reaction_slice_pre_window():
    from mcx.mcx_macro_reaction import slice_windows
    fx = json.load(open("data/macro_events/fixtures/historical_reaction_sep11_cpi.json", encoding="utf-8"))
    ev = datetime.fromisoformat(fx["event_time_utc"])
    obs = fx["observations"]["DXY"]
    windows = slice_windows(ev, obs)
    assert windows["PRE"]["status"] == "OK"
    assert windows["PRE"]["first"] == 104.10


def t13_historical_reaction_slice_r1():
    from mcx.mcx_macro_reaction import slice_windows
    fx = json.load(open("data/macro_events/fixtures/historical_reaction_sep11_cpi.json", encoding="utf-8"))
    ev = datetime.fromisoformat(fx["event_time_utc"])
    obs = fx["observations"]["DXY"]
    w = slice_windows(ev, obs)
    assert w["R1"]["status"] == "OK"
    # 12:31 and 12:35 inside R1 (0-5m after 12:30)
    assert w["R1"]["n"] == 2


def t14_historical_reaction_slice_r2():
    from mcx.mcx_macro_reaction import slice_windows
    fx = json.load(open("data/macro_events/fixtures/historical_reaction_sep11_cpi.json", encoding="utf-8"))
    ev = datetime.fromisoformat(fx["event_time_utc"])
    obs = fx["observations"]["DXY"]
    w = slice_windows(ev, obs)
    # 12:45 in R2 (5-15m), 12:35 exclusive end
    assert w["R2"]["status"] == "OK"


def t15_historical_reaction_slice_r3():
    from mcx.mcx_macro_reaction import slice_windows
    fx = json.load(open("data/macro_events/fixtures/historical_reaction_sep11_cpi.json", encoding="utf-8"))
    ev = datetime.fromisoformat(fx["event_time_utc"])
    obs = fx["observations"]["DXY"]
    w = slice_windows(ev, obs)
    # 13:00 in R3 (15-30m)
    assert w["R3"]["status"] == "OK"


def t16_historical_reaction_slice_r4():
    from mcx.mcx_macro_reaction import slice_windows
    fx = json.load(open("data/macro_events/fixtures/historical_reaction_sep11_cpi.json", encoding="utf-8"))
    ev = datetime.fromisoformat(fx["event_time_utc"])
    obs = fx["observations"]["DXY"]
    w = slice_windows(ev, obs)
    # 13:30 in R4 (30-60m)
    assert w["R4"]["status"] == "OK"


def t17_gold_reaction_direction():
    from mcx.mcx_macro_reaction import slice_windows
    fx = json.load(open("data/macro_events/fixtures/historical_reaction_sep11_cpi.json", encoding="utf-8"))
    ev = datetime.fromisoformat(fx["event_time_utc"])
    obs = fx["observations"]["COMEX_GOLD"]
    w = slice_windows(ev, obs)
    # Pre 4199.50 → R2 4185.00 (down)
    pre_last = w["PRE"]["last"]
    r2_last = w["R2"]["last"]
    assert r2_last < pre_last  # gold down


def t18_wti_reaction_direction():
    from mcx.mcx_macro_reaction import slice_windows
    fx = json.load(open("data/macro_events/fixtures/historical_reaction_sep11_cpi.json", encoding="utf-8"))
    ev = datetime.fromisoformat(fx["event_time_utc"])
    obs = fx["observations"]["WTI"]
    w = slice_windows(ev, obs)
    pre_last = w["PRE"]["last"]
    r2_last = w["R2"]["last"]
    assert r2_last < pre_last  # WTI down


def t19_reaction_capture_rejects_missing_event_time():
    from mcx.mcx_macro_reaction import capture_reaction, REASON_REACTION_DATA_UNAVAILABLE
    r = capture_reaction("DXY", None)
    assert r["status"] == REASON_REACTION_DATA_UNAVAILABLE


def t20_reaction_capture_uses_event_time():
    from mcx.mcx_macro_reaction import capture_reaction, REACTION_SYMBOLS
    # If we pass a historical event_time, provider query is anchored there
    # Weekend / network may fail; we check the request window is event-anchored
    ev = datetime(2026, 9, 11, 12, 30, tzinfo=UTC)
    r = capture_reaction("DXY", ev, mode="HISTORICAL")
    # Even if provider unavailable, we must not report MARKET_CLOSED
    assert r["status"] != "MARKET_CLOSED"
    assert "2026-09-11T12:05" in r.get("requested_start", "") or r["status"] in (
        "HISTORICAL_PROVIDER_UNAVAILABLE", "NETWORK_UNAVAILABLE", "SYMBOL_UNAVAILABLE")


def t21_reaction_reason_codes_complete():
    from mcx import mcx_macro_reaction as r
    for name in ("REASON_HISTORICAL_DATA_AVAILABLE",
                 "REASON_HISTORICAL_PROVIDER_UNAVAILABLE",
                 "REASON_NETWORK_UNAVAILABLE",
                 "REASON_SYMBOL_UNAVAILABLE",
                 "REASON_INTERVAL_UNAVAILABLE",
                 "REASON_INSUFFICIENT_PRE_EVENT_DATA",
                 "REASON_INSUFFICIENT_POST_EVENT_DATA",
                 "REASON_REACTION_DATA_UNAVAILABLE"):
        assert hasattr(r, name), f"missing {name}"


def t22_no_market_closed_label_in_reaction():
    with open(os.path.join(_SRC, "mcx", "mcx_macro_reaction.py"), encoding="utf-8") as f:
        src = f.read()
    assert "MARKET_CLOSED" not in src


def t23_wall_clock_not_used_for_anchor():
    with open(os.path.join(_SRC, "mcx", "mcx_macro_reaction.py"), encoding="utf-8") as f:
        src = f.read()
    # Must not use datetime.now() as the anchor for windowed fetch
    assert "datetime.now()" not in src.split("if __name__")[0]


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
