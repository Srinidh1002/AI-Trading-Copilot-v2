"""Section 7 P0-E — execution config authority. Quantity semantics verified live only."""
import json, os

CONFIG_PATH = "data/execution_evidence/mcx/exec_config.json"

# Default: UNVERIFIED until Monday Phase A confirms semantics
PRODUCT_EXEC_CONFIG = {
    "CRUDEOILM":  {"depth_quantity_semantics_verified": False, "depth_quantity_unit": None},
    "GOLDM":      {"depth_quantity_semantics_verified": False, "depth_quantity_unit": None},
    "NATGASMINI": {"depth_quantity_semantics_verified": False, "depth_quantity_unit": None},
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return dict(PRODUCT_EXEC_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(PRODUCT_EXEC_CONFIG)


def is_quantity_semantics_verified(product):
    cfg = load_config()
    return bool(cfg.get(product, {}).get("depth_quantity_semantics_verified", False))



def get_freshness_config(product):
    """Return (calibrated: bool, max_age_seconds: float|None) for a product.
    Reads from config JSON if present. Returns (False, None) if not."""
    cfg = load_config()
    p = cfg.get(product) or {}
    if p.get("execution_freshness_calibrated") and p.get("execution_quote_max_age_seconds"):
        try:
            return True, float(p["execution_quote_max_age_seconds"])
        except (TypeError, ValueError):
            return False, None
    return False, None


def is_freshness_calibrated(product):
    """True iff per-product freshness is calibrated in exec_config.json."""
    ok, _ = get_freshness_config(product)
    return ok


def get_execution_quote_max_age_seconds(product):
    """Return per-product max age in seconds, or None if uncalibrated."""
    ok, age = get_freshness_config(product)
    return age if ok else None


if __name__ == "__main__":
    print("CRUDEOILM verified:", is_quantity_semantics_verified("CRUDEOILM"))
    print("GOLDM verified:", is_quantity_semantics_verified("GOLDM"))
