"""Append-only breaking-news store — Section 6.37, 6.46."""
import json, os
from datetime import datetime, timezone

ROOT = "data/breaking_news"


def _event_dir(event_id):
    return os.path.join(ROOT, "normalized", event_id)


def save_event_version(event):
    """Append versioned event. Idempotent for identical hash."""
    os.makedirs(_event_dir(event["event_id"]), exist_ok=True)
    existing = list_versions(event["event_id"])
    new_hash = event.get("raw_payload_hash")
    for v in existing:
        if v.get("raw_payload_hash") == new_hash:
            return {"status": "UNCHANGED", "version": v.get("event_version")}
    new_version = (max((v.get("event_version", 1) for v in existing), default=0)) + 1
    ev = dict(event)
    ev["event_version"] = new_version
    if existing:
        ev["supersedes_event_version"] = max(v.get("event_version", 1) for v in existing)
    ev["stored_at"] = datetime.now(timezone.utc).isoformat()
    p = os.path.join(_event_dir(event["event_id"]), f"v{new_version}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ev, f, indent=2, default=str)
    return {"status": "APPENDED", "version": new_version}


def list_versions(event_id):
    d = _event_dir(event_id)
    if not os.path.exists(d):
        return []
    out = []
    for f in sorted(os.listdir(d)):
        if f.startswith("v") and f.endswith(".json"):
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    out.append(json.load(fh))
            except Exception:
                pass
    return out


def load_latest(event_id):
    versions = list_versions(event_id)
    if not versions:
        return None
    return max(versions, key=lambda v: v.get("event_version", 1))


def append_learning(record):
    p = os.path.join(ROOT, "learning", "breaking_outcomes.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def append_raw(event_id, raw_payload):
    os.makedirs(os.path.join(ROOT, "raw"), exist_ok=True)
    p = os.path.join(ROOT, "raw", f"{event_id}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, indent=2, default=str)


if __name__ == "__main__":
    print("mcx_breaking_store module loaded OK")
