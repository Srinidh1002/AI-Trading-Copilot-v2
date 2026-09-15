"""Append-only macro event store — Section 4.23, 4.27, 4.28."""
import json
import os
from datetime import datetime, timezone


STORE_ROOT = "data/macro_events"


def _event_path(event_id):
    return os.path.join(STORE_ROOT, "parsed", f"{event_id}.json")


def _versioned_path(event_id, revision):
    return os.path.join(STORE_ROOT, "parsed", f"{event_id}.rev{revision}.json")


def load_event(event_id):
    p = _event_path(event_id)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _next_revision(event_id):
    if not os.path.exists(os.path.join(STORE_ROOT, "parsed")):
        return 1
    existing = [f for f in os.listdir(os.path.join(STORE_ROOT, "parsed"))
                if f.startswith(f"{event_id}.rev")]
    if not existing:
        return 1
    return max(int(f.split(".rev")[1].split(".")[0]) for f in existing) + 1


def save_event(event):
    """Save as new revision. Preserves history. Idempotent for identical payloads."""
    os.makedirs(os.path.join(STORE_ROOT, "parsed"), exist_ok=True)
    eid = event["event_id"]

    # Check for identical existing
    existing = load_event(eid)
    if existing and json.dumps(existing, sort_keys=True, default=str) == \
                    json.dumps(event, sort_keys=True, default=str):
        return {"status": "UNCHANGED", "event_id": eid}

    # Determine revision
    rev = _next_revision(eid)
    event = dict(event)
    event["revision_number"] = rev
    if existing:
        event["supersedes_event_version"] = existing.get("revision_number", 1)
    event["stored_at"] = datetime.now(timezone.utc).isoformat()

    # Write versioned copy
    with open(_versioned_path(eid, rev), "w", encoding="utf-8") as f:
        json.dump(event, f, indent=2, default=str)
    # Overwrite current
    with open(_event_path(eid), "w", encoding="utf-8") as f:
        json.dump(event, f, indent=2, default=str)

    return {"status": "SAVED", "event_id": eid, "revision": rev}


def append_learning_record(record):
    """Append-only event-learning record — Section 4.32."""
    p = os.path.join(STORE_ROOT, "reactions", "event_outcomes.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


if __name__ == "__main__":
    print("mcx_macro_store module loaded OK")
