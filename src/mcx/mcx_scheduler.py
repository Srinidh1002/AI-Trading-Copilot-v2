"""MCX auto-scheduler — framework only. Manual invocation for now.
Will not auto-launch during certification (safety).
"""
from datetime import datetime, time as dtime


def _is_session_open(now=None):
    if now is None:
        now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 0) <= t < dtime(23, 15)


def pre_open_tasks():
    """Scheduled actions before 09:00 IST."""
    return [
        "refresh_instrument_master",
        "verify_angel_auth",
        "load_mcx_calendar",
        "print_presession_report",
        "health_check",
    ]


def in_session_tasks():
    """Every N seconds during session."""
    return ["cycle_decision", "monitor_positions", "log_decisions"]


def close_drain_tasks():
    """After 23:10 IST."""
    return ["block_new_entries", "close_open_positions", "reconcile_outcomes"]


def end_of_day_tasks():
    """After close."""
    return [
        "final_reconciliation",
        "certification_status",
        "learning_collect",
        "publish_daily_stats",
        "shutdown",
    ]


def status():
    now = datetime.now()
    return {
        "time": now.isoformat(timespec="seconds"),
        "session_open": _is_session_open(now),
        "pre_open": now.time() < dtime(9, 0),
        "close_drain": dtime(23, 10) <= now.time() < dtime(23, 15),
        "post_close": now.time() >= dtime(23, 15),
    }


if __name__ == "__main__":
    print("mcx_scheduler module loaded OK")
    print(status())
