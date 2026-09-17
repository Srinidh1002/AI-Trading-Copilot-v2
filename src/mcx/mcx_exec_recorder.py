"""Section 7.42-7.43 — bounded evidence recorder."""
import hashlib, json, os
from datetime import datetime, timezone

ROOT = "data/execution_evidence/mcx"


def _date_dir(product, date_iso):
    return os.path.join(ROOT, product.lower(), date_iso)


def record_quote(product, date_iso, quote):
    """Append one quote snapshot. Bounded to subscribed tokens by caller."""
    p = os.path.join(_date_dir(product, date_iso), "quotes.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(quote, default=str) + "\n")
    return p


def compute_evidence_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def record_quote_hash_addressed(product, date_iso, quote):
    """Store one quote at path keyed by its raw_payload_hash. Idempotent."""
    h = quote.get("raw_payload_hash")
    if not h:
        return None
    p = os.path.join(_date_dir(product, date_iso), "quotes", f"{h}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p):
        return p
    with open(p, "w", encoding="utf-8") as f:
        json.dump(quote, f, default=str, indent=2)
    return p


def load_quote_by_hash(product, date_iso, quote_hash):
    """Return stored quote dict or None."""
    if not quote_hash:
        return None
    p = os.path.join(_date_dir(product, date_iso), "quotes", f"{quote_hash}.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    print("mcx_exec_recorder loaded OK")
