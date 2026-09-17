"""MCX event risk — spec §22.
Minimal calendar stub with scheduled high-impact events for crude oil.
Events are approximate; verify against official EIA/OPEC calendars before promoting.
"""
from datetime import datetime, time as dtime


# Weekly recurring: EIA petroleum status report — Wednesdays ~20:00 IST
# Monthly/irregular: OPEC meetings — see official calendar
# This is a STARTER. Add real calendar entries as they are confirmed.
SCHEDULED_EVENTS = [
    # (day_of_week, hour, minute, name, block_before_min, block_after_min)
    # EIA crude oil inventories — Wed 20:00 IST
    (2, 20, 0, "EIA_CRUDE_INVENTORIES", 15, 15),
    # EIA natural gas storage — Thu 20:00 IST
    (3, 20, 0, "EIA_NATGAS_STORAGE", 15, 15),
]


def _minutes_until(now, target_hm):
    target = datetime.combine(now.date(), target_hm)
    if target < now:
        return None
    return int((target - now).total_seconds() / 60)


def get_state(now=None):
    """Returns dict with state, next_event, minutes_until."""
    if now is None:
        now = datetime.now()
    best = None
    best_minutes = None

    for dow, hh, mm, name, before, after in SCHEDULED_EVENTS:
        if now.weekday() != dow:
            continue
        target = dtime(hh, mm)
        mins = _minutes_until(now, target)
        if mins is None or mins < 0:
            # Check if we're inside post-event window
            target_dt = datetime.combine(now.date(), target)
            elapsed = int((now - target_dt).total_seconds() / 60)
            if 0 <= elapsed <= after:
                return {
                    "state": "POST_EVENT",
                    "event": name,
                    "minutes_since": elapsed,
                    "block_entries": False,  # post-event: allow after stabilization
                }
            continue
        if best_minutes is None or mins < best_minutes:
            best_minutes = mins
            best = (name, before, after)

    if best is None:
        return {"state": "NORMAL", "event": None, "minutes_until": None, "block_entries": False}

    name, before, after = best
    if best_minutes <= before:
        return {
            "state": "PRE_EVENT",
            "event": name,
            "minutes_until": best_minutes,
            "block_entries": True,
        }
    return {
        "state": "NORMAL",
        "event": name,
        "minutes_until": best_minutes,
        "block_entries": False,
    }


def describe(state):
    if state["state"] == "NORMAL":
        if state.get("event"):
            return f"NORMAL (next {state['event']} in {state['minutes_until']}m)"
        return "NORMAL"
    if state["state"] == "PRE_EVENT":
        return f"PRE_EVENT {state['event']} in {state['minutes_until']}m — entries blocked"
    if state["state"] == "POST_EVENT":
        return f"POST_EVENT {state['event']} +{state['minutes_since']}m"
    return state["state"]


if __name__ == "__main__":
    s = get_state()
    print(f"MCX event risk: {describe(s)}")
