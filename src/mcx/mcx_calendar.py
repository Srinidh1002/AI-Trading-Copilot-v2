"""MCX session/expiry resolver — spec §6, §35.
Sessions: 09:00–23:30 default; 09:00–23:55 during US DST (approx Apr–Oct).
Holidays: check against a maintained list. If uncertain, fail CLOSED (no entries).
"""
from datetime import datetime, date, time as dtime


# Holidays imported from centralized module
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_SRC = _os.path.dirname(_HERE)
if _SRC not in _sys.path:
    _sys.path.insert(0, _SRC)
from mcx.mcx_holidays import MCX_HOLIDAYS_2026, is_holiday


def _is_us_dst(d: date) -> bool:
    """US DST roughly 2nd Sun March -> 1st Sun November."""
    if d.month < 3 or d.month > 11:
        return False
    if d.month == 3:
        # 2nd Sunday of March
        days = [x for x in range(1, 32) if date(d.year, 3, x).weekday() == 6]
        return d.day >= days[1]
    if d.month == 11:
        # 1st Sunday of November
        days = [x for x in range(1, 8) if date(d.year, 11, x).weekday() == 6]
        return d.day < days[0]
    return True


def get_session(now=None):
    """Returns dict: status, tradable, close_time, note."""
    if now is None:
        now = datetime.now()

    wd = now.weekday()
    if wd >= 5:
        return {"status": "WEEKEND", "tradable": False, "close_time": None, "note": "Sat/Sun"}

    # Holiday check (centralized)
    kind, name = is_holiday(now.year, now.month, now.day)
    if kind == "FULL":
        return {"status": "HOLIDAY", "tradable": False,
                "close_time": None, "note": name}
    if kind == "MORNING_ONLY" and now.time() < dtime(17, 0):
        return {"status": "HOLIDAY_MORNING_CLOSED", "tradable": False,
                "close_time": dtime(23, 30), "note": f"{name} morning closed"}

    # MCX rule: internationally referenceable non-agri commodities
    #   US DST active (spring -> fall): close 23:30
    #   US DST inactive (fall -> spring): close 23:55
    # Reference: MCX market-operations FAQ
    if _is_us_dst(now.date()):
        close_t = dtime(23, 30)
    else:
        close_t = dtime(23, 55)

    t = now.time()
    if t < dtime(9, 0):
        return {"status": "PRE_OPEN", "tradable": False, "close_time": close_t,
                "note": "before 09:00"}
    if t >= dtime(23, 15):
        return {"status": "CLOSE_BUFFER", "tradable": False, "close_time": close_t,
                "note": "after 23:15 — no new entries"}
    if t >= close_t:
        return {"status": "CLOSED", "tradable": False, "close_time": close_t,
                "note": "after close"}

    # Add morning/evening phase
    phase = "MORNING" if t < dtime(17, 0) else "EVENING"
    return {"status": "OPEN", "tradable": True, "close_time": close_t,
            "note": f"{phase} session", "phase": phase}


def option_expiry_safety(option_expiry, underlying_futures_expiry, now=None):
    """Spec §35: block new entries inside expiry-risk window.
    Returns dict: allow_new_entries, days_to_expiry, note.
    """
    if now is None:
        now = datetime.now().date()
    if isinstance(option_expiry, str):
        try:
            option_expiry = datetime.strptime(option_expiry, "%Y-%m-%d").date()
        except Exception:
            return {"allow_new_entries": False, "days_to_expiry": None,
                    "note": "OPTION_EXPIRY_UNPARSEABLE"}
    dte = (option_expiry - now).days if option_expiry else None

    # MCX option exercise window: block entries within 1 calendar day of expiry
    if dte is None:
        return {"allow_new_entries": False, "days_to_expiry": None,
                "note": "DTE_UNKNOWN"}
    if dte <= 1:
        return {"allow_new_entries": False, "days_to_expiry": dte,
                "note": f"DTE_{dte}_EXPIRY_RISK"}
    if dte <= 2:
        return {"allow_new_entries": True, "days_to_expiry": dte,
                "note": f"DTE_{dte}_CAUTION"}
    return {"allow_new_entries": True, "days_to_expiry": dte, "note": "OK"}


if __name__ == "__main__":
    s = get_session()
    print(f"session: {s}")
    e = option_expiry_safety("2026-09-17", "2026-09-21")
    print(f"expiry safety (Tue→Thu): {e}")
