"""Section 7.17, 7.27-7.30 — lifecycle state machine. Pure / testable."""
import json, os, sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

LIFECYCLE_STATES = (
    "FLAT", "ENTRY_CANDIDATE", "EXECUTION_QUOTE_VALIDATED",
    "PAPER_OPEN", "MONITORING", "EXIT_TRIGGERED", "EXIT_PENDING",
    "EXIT_QUOTE_VALIDATED", "PAPER_CLOSED", "RECONCILING",
    "RECONCILED", "COUNTABLE", "NON_COUNTABLE",
    "DATA_DEGRADED", "RECOVERY_ONLY", "RECONCILIATION_PENDING",
)

# Valid transitions
ALLOWED = {
    "FLAT": {"ENTRY_CANDIDATE", "RECOVERY_ONLY"},
    "RECOVERY_ONLY": {"MONITORING", "RECONCILING", "FLAT"},
    "ENTRY_CANDIDATE": {"EXECUTION_QUOTE_VALIDATED", "FLAT"},
    "EXECUTION_QUOTE_VALIDATED": {"PAPER_OPEN", "FLAT"},
    "PAPER_OPEN": {"MONITORING", "DATA_DEGRADED"},
    "MONITORING": {"EXIT_TRIGGERED", "DATA_DEGRADED"},
    "EXIT_TRIGGERED": {"EXIT_PENDING", "EXIT_QUOTE_VALIDATED"},
    "EXIT_PENDING": {"EXIT_QUOTE_VALIDATED", "DATA_DEGRADED"},
    "EXIT_QUOTE_VALIDATED": {"PAPER_CLOSED"},
    "PAPER_CLOSED": {"RECONCILING"},
    "RECONCILING": {"RECONCILED", "RECONCILIATION_PENDING"},
    "RECONCILED": {"COUNTABLE", "NON_COUNTABLE"},
    "RECONCILIATION_PENDING": {"RECONCILING", "NON_COUNTABLE"},
    "DATA_DEGRADED": {"MONITORING", "RECONCILIATION_PENDING"},
}


def transition(current, new, reason, evidence_id=None, timestamp_iso=None):
    """Return dict of transition or raise ValueError on illegal move."""
    if new not in LIFECYCLE_STATES:
        raise ValueError(f"UNKNOWN_STATE:{new}")
    if current not in LIFECYCLE_STATES:
        raise ValueError(f"UNKNOWN_STATE:{current}")
    if new not in ALLOWED.get(current, set()):
        raise ValueError(f"ILLEGAL_TRANSITION:{current}->{new}")
    return {
        "state_before": current,
        "state_after": new,
        "reason": reason,
        "evidence_id": evidence_id,
        "timestamp": timestamp_iso or datetime.now(timezone.utc).isoformat(),
    }


def apply_transition(pos, transition_dict):
    """Mutate pos dict in place (caller persists atomically)."""
    if "lifecycle_history" not in pos:
        pos["lifecycle_history"] = []
    pos["lifecycle_history"].append(transition_dict)
    pos["lifecycle_state"] = transition_dict["state_after"]
    return pos


if __name__ == "__main__":
    print("States:", len(LIFECYCLE_STATES))
    t = transition("FLAT", "ENTRY_CANDIDATE", "test")
    print("OK:", t["state_before"], "->", t["state_after"])
    try:
        transition("FLAT", "PAPER_OPEN", "illegal")
        print("FAIL: should have raised")
    except ValueError as e:
        print("Correctly rejected:", e)
