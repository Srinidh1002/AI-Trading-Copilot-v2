"""Append-only fundamental store — Section 5.27, 5.31."""
import json
import os
from datetime import datetime, timezone

STORE_ROOT = "data/fundamentals"


def _obs_path(product, metric_id):
    return os.path.join(STORE_ROOT, product.lower(), f"{metric_id}.jsonl")


def save_observation(obs):
    """Append-only. Idempotent for identical hash."""
    p = _obs_path(obs["product"], obs["metric_id"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    # Idempotency check
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    try:
                        existing = json.loads(line)
                    except Exception:
                        continue
                    if existing.get("raw_payload_hash") == obs.get("raw_payload_hash"):
                        return {"status": "UNCHANGED", "path": p}
        except Exception:
            pass
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obs, default=str) + "\n")
    return {"status": "APPENDED", "path": p}


def append_learning_record(record):
    """Section 5.31 — append-only learning."""
    p = os.path.join(STORE_ROOT, "learning", "fundamental_outcomes.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def count_observations(product):
    root = os.path.join(STORE_ROOT, product.lower())
    if not os.path.exists(root):
        return 0
    n = 0
    for f in os.listdir(root):
        if f.endswith(".jsonl"):
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                n += sum(1 for _ in fh)
    return n


if __name__ == "__main__":
    print("mcx_fundamental_store module loaded OK")
