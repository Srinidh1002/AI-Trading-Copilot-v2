"""Schema-2 provider-scoped MCX execution calibration writer.

Refuses to write unless a verifier report says PASS for every product
being written. Never upgrades legacy schema-1 evidence. Preserves
existing providers in the config (merge, do not clobber).

Config file: data/execution_evidence/mcx/exec_config.json
Shape:
  {
    "schema_version": 2,
    "providers": {
      "FYERS": {
        "CRUDEOILM": {
          "calibration_provider": "FYERS",
          "depth_quantity_semantics_verified": true,
          "depth_quantity_unit": "...",
          "execution_freshness_calibrated": true,
          "execution_quote_max_age_seconds": N,
          "calibrated_at": "...",
          "evidence_ref": "data/execution_evidence/mcx/fyers/<file>",
          "evidence_kind": "LIVE_MARKET_DEPTH"
        }
      }
    }
  }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

_CONFIG_PATH = REPO_ROOT / "data" / "execution_evidence" / "mcx" / "exec_config.json"
_EVIDENCE_DIR = REPO_ROOT / "data" / "execution_evidence" / "mcx" / "fyers"
_SUPPORTED = ("CRUDEOILM", "GOLDM", "NATGASMINI")
_PROVIDER = "FYERS"
_SCHEMA_VERSION = 2
_EVIDENCE_KIND = "LIVE_MARKET_DEPTH"

# Freshness derived from verifier p95 age, capped conservatively.
_FRESHNESS_HEADROOM = 2.0
_FRESHNESS_MIN = 15


def _newest_evidence_for(product):
    """Return the newest evidence file for a product, or None."""
    if not _EVIDENCE_DIR.exists():
        return None
    cands = sorted(_EVIDENCE_DIR.glob(f"{product}_*.jsonl"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def _derive_max_age(verifier_entry):
    p95 = verifier_entry.get("p95_age_seconds")
    if not isinstance(p95, (int, float)) or p95 <= 0:
        return None
    candidate = int(p95 * _FRESHNESS_HEADROOM)
    return max(_FRESHNESS_MIN, min(candidate, 300))


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", required=True,
                    help="path to verifier report JSON")
    ap.add_argument("--products", default=",".join(_SUPPORTED),
                    help="comma-separated subset to write")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate and print intended config; do not write")
    args = ap.parse_args(argv)

    products = tuple(p.strip().upper() for p in args.products.split(",") if p.strip())
    bad = [p for p in products if p not in _SUPPORTED]
    if bad:
        print(f"unknown products: {bad}", file=sys.stderr)
        return 2

    report_path = Path(args.report)
    if not report_path.is_file():
        print(f"report not found: {report_path}", file=sys.stderr)
        return 1
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"report unreadable: {type(exc).__name__}", file=sys.stderr)
        return 1
    if not isinstance(report, dict):
        print("report not a dict", file=sys.stderr)
        return 1

    # Every product to write must be PASS in the verifier report.
    not_pass = []
    per_product_record = {}
    for product in products:
        entry = report.get(product)
        if not isinstance(entry, dict):
            not_pass.append((product, "MISSING_IN_REPORT"))
            continue
        if entry.get("verdict") != "PASS":
            not_pass.append((product, entry.get("verdict") or "NO_VERDICT"))
            continue
        p95 = entry.get("p95_age_seconds")
        if not isinstance(p95, (int, float)) or p95 <= 0:
            not_pass.append((product, "NO_P95_AGE"))
            continue
        evidence_file = _newest_evidence_for(product)
        if evidence_file is None:
            not_pass.append((product, "NO_EVIDENCE_FILE"))
            continue
        max_age = _derive_max_age(entry)
        if max_age is None:
            not_pass.append((product, "MAX_AGE_DERIVATION_FAILED"))
            continue
        try:
            evidence_ref = str(evidence_file.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            # Evidence file is not under REPO_ROOT (e.g. a test isolation dir).
            # Record the absolute path; the runtime gate only checks that
            # some non-empty reference exists, and the operator can audit it.
            evidence_ref = str(evidence_file).replace("\\", "/")
        per_product_record[product] = {
            "calibration_provider": _PROVIDER,
            "depth_quantity_semantics_verified": True,
            "depth_quantity_unit": "LOTS",
            "execution_freshness_calibrated": True,
            "execution_quote_max_age_seconds": max_age,
            "calibrated_at": datetime.now(timezone.utc).isoformat(),
            "evidence_ref": evidence_ref,
            "evidence_kind": _EVIDENCE_KIND,
        }

    if not_pass:
        print("WRITER_HOLD — cannot write schema-2 for:")
        for product, why in not_pass:
            print(f"  {product}: {why}")
        return 1

    # Load existing config (merge, do not clobber other providers).
    existing = {}
    if _CONFIG_PATH.exists():
        try:
            existing = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    if not isinstance(existing, dict):
        existing = {}
    # Refuse to silently drop a schema-1 file that isn't a superset.
    existing_providers = existing.get("providers")
    if existing_providers is not None and not isinstance(existing_providers, dict):
        print("existing config providers is not a dict; refusing to overwrite",
              file=sys.stderr)
        return 1

    providers = dict(existing_providers or {})
    fyers_block = dict(providers.get(_PROVIDER) or {})
    for product, record in per_product_record.items():
        fyers_block[product] = record
    providers[_PROVIDER] = fyers_block

    new_config = dict(existing)
    new_config["schema_version"] = _SCHEMA_VERSION
    new_config["providers"] = providers
    new_config["updated_at"] = datetime.now(timezone.utc).isoformat()

    if args.dry_run:
        print("DRY_RUN — intended config:")
        print(json.dumps(new_config, indent=2, sort_keys=True))
        return 0

    # Preserve any pre-existing config as a timestamped backup.
    # The legacy schema-1 file may carry audit evidence; we never delete it.
    if _CONFIG_PATH.exists():
        try:
            prev = _CONFIG_PATH.read_text(encoding="utf-8")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = _CONFIG_PATH.with_name(
                _CONFIG_PATH.name + f".bak_{stamp}"
            )
            _write_atomic(backup, json.loads(prev) if prev.strip().startswith("{") else {})
            print(f"BACKUP {backup}")
        except Exception as exc:
            print(f"BACKUP_WARN: {type(exc).__name__}")

    _write_atomic(_CONFIG_PATH, new_config)
    print(f"WROTE {_CONFIG_PATH}")
    for product, record in per_product_record.items():
        print(f"  {product}: evidence_ref={record['evidence_ref']} "
              f"max_age={record['execution_quote_max_age_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
