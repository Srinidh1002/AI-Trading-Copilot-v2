"""Schema-2 provider-scoped MCX execution calibration writer.

Refuses to write unless a verifier report says PASS for every product
being written. Uses the verifier's verified_quantity_unit; never
hard-codes LOTS. Preserves existing providers in the config (merge, do
not clobber). Backs up any prior exec_config.json. Never converts
legacy schema-1 evidence into PASS.

Config file: data/execution_evidence/mcx/exec_config.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
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

_FRESHNESS_HEADROOM = 2.0
_FRESHNESS_MIN = 15
_FRESHNESS_MAX = 300


def _newest_evidence_for(product):
    if not _EVIDENCE_DIR.exists():
        return None
    cands = sorted(
        _EVIDENCE_DIR.glob(f"{product}_*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return cands[0] if cands else None


def _derive_max_age(verifier_entry):
    """Derive the runtime execution-quote max age from Option D evidence.

    Option D retires the equity-index-style provider-feed freshness
    concept. The synchronous FYERS depth response is observed locally
    at depth_received_at; snapshot age is the local observation age.
    The runtime max_age_seconds is the conservative ceiling under which
    a freshly observed depth snapshot is considered execution-valid.

    A snapshot observed milliseconds before evaluation is fresh by
    construction. We still cap conservatively so a paused collector or
    a stale replay cannot be admitted. The p95_age_seconds field from
    the old gate is not required and is intentionally ignored.
    """
    # If a summary snapshot age is present, bound by it.
    freshness = verifier_entry.get("reported", {}).get("DEPTH_OBSERVATION_FRESHNESS")
    snapshot_max = None
    if isinstance(freshness, str) and "max_snapshot_age_s=" in freshness:
        try:
            snapshot_max = float(freshness.split("max_snapshot_age_s=", 1)[1].strip())
        except (ValueError, IndexError):
            snapshot_max = None

    # snapshot_max is the observed max local observation age. A value
    # of 0.0 is legitimate: the depth snapshot was evaluated at the same
    # instant it was recorded. Negative values indicate corrupt evidence.
    if snapshot_max is None or snapshot_max < 0:
        return None

    candidate = int(snapshot_max * _FRESHNESS_HEADROOM)
    return max(_FRESHNESS_MIN, min(candidate, _FRESHNESS_MAX))


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
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
    ap.add_argument("--report", required=True, help="path to verifier report JSON")
    ap.add_argument(
        "--products",
        default=",".join(_SUPPORTED),
        help="comma-separated subset to write",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print intended config; do not write",
    )
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

        unit = entry.get("verified_quantity_unit")
        if not isinstance(unit, str) or not unit.strip():
            not_pass.append((product, "NO_VERIFIED_QUANTITY_UNIT"))
            continue
        unit = unit.strip()
        if unit == "LOTS":
            # Option D forbids hard-coded LOTS: FYERS does not publish an
            # authoritative unit proof in the SDK surface we use.
            not_pass.append((product, "FORBIDDEN_QUANTITY_UNIT_LOTS"))
            continue

        # Option D: the required freshness signal is the synchronous
        # depth-snapshot observation. Verify the verifier entry agrees.
        basis = entry.get("depth_freshness_basis")
        if basis != "SYNCHRONOUS_FYERS_DEPTH_RESPONSE":
            not_pass.append((product, f"BAD_DEPTH_FRESHNESS_BASIS:{basis!r}"))
            continue
        reported = entry.get("reported") or {}
        freshness = reported.get("DEPTH_OBSERVATION_FRESHNESS")
        if not (isinstance(freshness, str) and "max_snapshot_age_s=" in freshness):
            not_pass.append((product, "NO_SNAPSHOT_FRESHNESS"))
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
            evidence_ref = str(evidence_file).replace("\\", "/")

        record = {
            "calibration_provider": _PROVIDER,
            "depth_quantity_semantics_verified": True,
            "depth_quantity_unit": unit,
            "execution_freshness_calibrated": True,
            "execution_quote_max_age_seconds": max_age,
            "depth_freshness_basis": ("SYNCHRONOUS_FYERS_DEPTH_RESPONSE"),
            "depth_provider_timestamp_available": bool(
                reported.get("PROVIDER_DEPTH_TIMESTAMP_AVAILABLE", False)
            ),
            "last_trade_timestamp_source": reported.get("LAST_TRADE_TIMESTAMP_SOURCE"),
            "calibrated_at": datetime.now(UTC).isoformat(),
            "evidence_ref": evidence_ref,
            "evidence_kind": _EVIDENCE_KIND,
        }
        basis = entry.get("quantity_unit_basis")
        if isinstance(basis, str) and basis.strip():
            record["quantity_unit_basis"] = basis.strip()
        per_product_record[product] = record

    if not_pass:
        print("WRITER_HOLD — cannot write schema-2 for:")
        for product, why in not_pass:
            print(f"  {product}: {why}")
        return 1

    existing = {}
    if _CONFIG_PATH.exists():
        try:
            existing = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing_providers = existing.get("providers")
    if existing_providers is not None and not isinstance(existing_providers, dict):
        print(
            "existing config providers is not a dict; refusing to overwrite",
            file=sys.stderr,
        )
        return 1

    providers = dict(existing_providers or {})
    fyers_block = dict(providers.get(_PROVIDER) or {})
    for product, record in per_product_record.items():
        fyers_block[product] = record
    providers[_PROVIDER] = fyers_block

    new_config = dict(existing)
    new_config["schema_version"] = _SCHEMA_VERSION
    new_config["providers"] = providers
    new_config["updated_at"] = datetime.now(UTC).isoformat()

    if args.dry_run:
        print("DRY_RUN — intended config:")
        print(json.dumps(new_config, indent=2, sort_keys=True))
        return 0

    if _CONFIG_PATH.exists():
        try:
            prev = _CONFIG_PATH.read_text(encoding="utf-8")
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup = _CONFIG_PATH.with_name(_CONFIG_PATH.name + f".bak_{stamp}")
            _write_atomic(backup, json.loads(prev) if prev.strip().startswith("{") else {})
            print(f"BACKUP {backup}")
        except Exception as exc:
            print(f"BACKUP_WARN: {type(exc).__name__}")

    _write_atomic(_CONFIG_PATH, new_config)
    print(f"WROTE {_CONFIG_PATH}")
    for product, record in per_product_record.items():
        print(
            f"  {product}: unit={record['depth_quantity_unit']} "
            f"evidence_ref={record['evidence_ref']} "
            f"max_age={record['execution_quote_max_age_seconds']}s"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
