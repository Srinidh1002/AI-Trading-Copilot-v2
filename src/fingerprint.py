"""Data Fingerprinting - Hash evidence snapshots for audit trail."""
import hashlib
import json
from typing import Any


def fingerprint(obj: Any) -> str:
    """Return short hash of any serializable object."""
    try:
        if isinstance(obj, (dict, list)):
            s = json.dumps(obj, sort_keys=True, default=str)
        else:
            s = str(obj)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return "UNKNOWN"


def fingerprint_snapshot(**kwargs) -> str:
    """Fingerprint a snapshot from keyword arguments."""
    return fingerprint(kwargs)


if __name__ == "__main__":
    # Test determinism
    s1 = {"nifty": 23450.5, "stocks": [("HDFCBANK", 0.5), ("ICICI", -0.3)], "pcr": 1.2}
    s2 = {"pcr": 1.2, "stocks": [("HDFCBANK", 0.5), ("ICICI", -0.3)], "nifty": 23450.5}
    s3 = {"nifty": 23451.0, "stocks": [("HDFCBANK", 0.5)], "pcr": 1.2}
    
    print(f"snap1: {fingerprint(s1)}")
    print(f"snap2: {fingerprint(s2)}  (order-independent)")
    print(f"snap3: {fingerprint(s3)}  (different data)")
    print(f"match12: {fingerprint(s1) == fingerprint(s2)}")
    print(f"match13: {fingerprint(s1) == fingerprint(s3)}")
