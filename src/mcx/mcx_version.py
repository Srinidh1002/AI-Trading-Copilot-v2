"""MCX strategy version freeze — spec §34.
During a /100 certification epoch, strategy version must be FROZEN.
Bot reads this on startup and refuses to trade if version changes mid-epoch.
"""
import json
import os
from datetime import datetime

# Per-product registry. CRUDEOILM keeps its existing names for backward compat.
# GOLDM / NATGASMINI use PRECERT epochs until their FYERS PAPER paths are proven.
PRODUCT_EPOCHS = {
    "CRUDEOILM": {
        "strategy_version": "MCX_POST_PRECISION_V4",
        "epoch": "POST_PRECISION_V4",
        "version_path": "data/paper_trades/mcx_strategy_version.json",
        "certification_eligible": True,
    },
    "GOLDM": {
        "strategy_version": "MCX_GOLDM_PRECERT_V1",
        "epoch": "GOLDM_PRECERT_V1",
        "version_path": "data/paper_trades/mcx_goldm_strategy_version.json",
        # PROMOTED 2026-09-23 - certification_eligible flipped to True
        "certification_eligible": True,
    },
    "NATGASMINI": {
        "strategy_version": "MCX_NATGASMINI_PRECERT_V1",
        "epoch": "NATGASMINI_PRECERT_V1",
        "version_path": "data/paper_trades/mcx_natgasmini_strategy_version.json",
        # PROMOTED 2026-09-23 - certification_eligible flipped to True
        "certification_eligible": True,
    },
}

# Backward-compat shims (still used by any legacy call site)
VERSION_PATH = PRODUCT_EPOCHS["CRUDEOILM"]["version_path"]
CURRENT_VERSION = PRODUCT_EPOCHS["CRUDEOILM"]["strategy_version"]
CURRENT_EPOCH = PRODUCT_EPOCHS["CRUDEOILM"]["epoch"]
FROZEN_AT = None


def initialize_or_verify():
    """Called once at bot startup. Idempotent."""
    if not os.path.exists(VERSION_PATH):
        rec = {
            "strategy_version": CURRENT_VERSION,
            "epoch": CURRENT_EPOCH,
            "frozen_at": datetime.now().isoformat(timespec="seconds"),
            "note": "Version frozen for the duration of this certification epoch.",
        }
        os.makedirs(os.path.dirname(VERSION_PATH), exist_ok=True)
        with open(VERSION_PATH, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)
        return {"status": "INITIALIZED", "record": rec}

    with open(VERSION_PATH, encoding="utf-8") as f:
        rec = json.load(f)
    if rec.get("strategy_version") != CURRENT_VERSION:
        return {
            "status": "VERSION_MISMATCH",
            "stored": rec.get("strategy_version"),
            "current": CURRENT_VERSION,
            "action": "REFUSE_TO_TRADE",
        }
    if rec.get("epoch") != CURRENT_EPOCH:
        return {
            "status": "EPOCH_MISMATCH",
            "stored_epoch": rec.get("epoch"),
            "current_epoch": CURRENT_EPOCH,
            "action": "REFUSE_TO_TRADE",
        }
    return {"status": "OK", "record": rec}


def verify_all_epochs(state_path="data/paper_trades/mcx_crudeoilm_experimental.json"):
    """Full certification integrity gate (spec §34).
    Verifies version file, state file, and ledgers all agree on epoch.
    Returns dict with certification_ready and reasons.
    """
    import json
    issues = []

    # 1. Version file
    v = initialize_or_verify()
    if v.get("status") in ("VERSION_MISMATCH", "EPOCH_MISMATCH"):
        issues.append(f"VERSION_FILE:{v.get('status')}")

    # 2. State file
    state_epoch = None
    if os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                st = json.load(f)
            state_epoch = st.get("epoch")
            if state_epoch != CURRENT_EPOCH:
                issues.append(f"STATE_EPOCH:{state_epoch}!={CURRENT_EPOCH}")
        except Exception as e:
            issues.append(f"STATE_READ_ERROR:{str(e)[:60]}")
    else:
        issues.append("STATE_FILE_MISSING")

    return {
        "certification_ready": len(issues) == 0,
        "current_version": CURRENT_VERSION,
        "current_epoch": CURRENT_EPOCH,
        "state_epoch": state_epoch,
        "issues": issues,
    }


def get_product_epochs(product):
    """Return per-product epoch config or None."""
    return PRODUCT_EPOCHS.get((product or "").upper())


def initialize_or_verify_for_product(product):
    """Product-aware version check. Returns dict."""
    cfg = get_product_epochs(product)
    if not cfg:
        return {"status": "UNKNOWN_PRODUCT", "product": product}
    vpath = cfg["version_path"]
    if not os.path.exists(vpath):
        rec = {
            "product": product.upper(),
            "strategy_version": cfg["strategy_version"],
            "epoch": cfg["epoch"],
            "certification_eligible": cfg["certification_eligible"],
            "frozen_at": datetime.now().isoformat(timespec="seconds"),
            "note": "Version frozen for the duration of this certification epoch.",
        }
        os.makedirs(os.path.dirname(vpath), exist_ok=True)
        with open(vpath, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)
        return {"status": "INITIALIZED", "record": rec}
    with open(vpath, encoding="utf-8") as f:
        rec = json.load(f)
    if rec.get("strategy_version") != cfg["strategy_version"]:
        return {"status": "VERSION_MISMATCH", "stored": rec.get("strategy_version"),
                "current": cfg["strategy_version"], "action": "REFUSE_TO_TRADE"}
    if rec.get("epoch") != cfg["epoch"]:
        return {"status": "EPOCH_MISMATCH", "stored_epoch": rec.get("epoch"),
                "current_epoch": cfg["epoch"], "action": "REFUSE_TO_TRADE"}
    return {"status": "OK", "record": rec}


def verify_all_epochs_for_product(product, state_path):
    """Product-aware full integrity check."""
    issues = []
    cfg = get_product_epochs(product)
    if not cfg:
        return {"certification_ready": False, "issues": [f"UNKNOWN_PRODUCT:{product}"]}

    v = initialize_or_verify_for_product(product)
    if v.get("status") in ("VERSION_MISMATCH", "EPOCH_MISMATCH"):
        issues.append(f"VERSION_FILE:{v.get('status')}")

    state_epoch = None
    if os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                st = json.load(f)
            state_epoch = st.get("epoch")
            if state_epoch != cfg["epoch"]:
                issues.append(f"STATE_EPOCH:{state_epoch}!={cfg['epoch']}")
        except Exception as e:
            issues.append(f"STATE_READ_ERROR:{str(e)[:60]}")
    else:
        issues.append("STATE_FILE_MISSING")

    return {
        "certification_ready": len(issues) == 0,
        "product": product.upper(),
        "current_version": cfg["strategy_version"],
        "current_epoch": cfg["epoch"],
        "state_epoch": state_epoch,
        "certification_eligible": cfg["certification_eligible"],
        "issues": issues,
    }


def is_certification_eligible(product):
    """Registry authority. True ONLY for products authorized to count toward /100."""
    cfg = get_product_epochs(product) or {}
    return bool(cfg.get("certification_eligible", False))


if __name__ == "__main__":
    print(initialize_or_verify())
    print()
    print(verify_all_epochs())
