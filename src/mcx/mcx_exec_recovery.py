"""Section 7.27-7.28 — restart recovery + idempotency."""
import json, os

def check_open_position(state):
    """Return dict indicating whether recovery is required."""
    pos = state.get("active_position")
    if not pos:
        return {"recovery_required": False}
    return {
        "recovery_required": True,
        "mode": "RECOVERY_ONLY",
        "position": pos,
    }


def recovery_status(state, product):
    """Return whether new entries may proceed."""
    r = check_open_position(state)
    return {
        "product": product,
        "recovery_required": r["recovery_required"],
        "new_entries_allowed": not r["recovery_required"],
    }


if __name__ == "__main__":
    print("with position:", check_open_position({"active_position": {"trade_id": "T1"}}))
    print("flat:", check_open_position({"active_position": None}))
