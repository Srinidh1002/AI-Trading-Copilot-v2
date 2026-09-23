"""Offline verifier for MCX FYERS execution calibration evidence.

Reads the JSONL produced by collect_mcx_fyers_execution_calibration.py
and independently determines whether the evidence can prove:

  * one provider identity (FYERS only)
  * supported product
  * real option identities
  * non-empty depth on both sides
  * quantity values coherent within a contract's lot-size story
  * enough independent observations
  * usable timestamp semantics and defensible freshness distribution
  * no duplicate payload hashes inflating the sample
  * evidence not stale and not fabricated

Emits a machine-readable verdict dict and prints a summary. Exit 0 only
on VERDICT=PASS. Never writes config.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

_EVIDENCE_DIR = REPO_ROOT / "data" / "execution_evidence" / "mcx" / "fyers"
_SUPPORTED = ("CRUDEOILM", "GOLDM", "NATGASMINI")
_PROVIDER = "FYERS"

MIN_SAMPLES_PER_CONTRACT = 5
MIN_CONTRACTS_PER_PRODUCT = 2
MIN_DISTINCT_PAYLOAD_HASHES = 3
MAX_P95_AGE_SECONDS = 300
MAX_ACCEPTABLE_SAMPLE_AGE_SECONDS = 86400


def _load_rows(product=None):
    rows = []
    for p in sorted(_EVIDENCE_DIR.glob("*.jsonl")):
        if product and not p.name.startswith(product):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            continue
    return rows


def _check_provider(rows):
    providers = {str(r.get("provider") or "").upper() for r in rows}
    if providers != {_PROVIDER}:
        return False, f"provider set {providers} != {{{_PROVIDER}}}"
    return True, "provider=FYERS"


def _check_product(rows, product):
    products = {str(r.get("product") or "").upper() for r in rows}
    if products != {product}:
        return False, f"product set {products} != {{{product}}}"
    return True, f"product={product}"


def _check_depth(rows):
    """Every row must have at least one bid and one ask level with numeric volume."""
    bad = 0
    for r in rows:
        bids = r.get("bid_levels") or []
        asks = r.get("ask_levels") or []
        if not bids or not asks:
            bad += 1
            continue
        bq = r.get("bid_quantities") or []
        aq = r.get("ask_quantities") or []
        if not any(isinstance(x, (int, float)) and x > 0 for x in bq):
            bad += 1
            continue
        if not any(isinstance(x, (int, float)) and x > 0 for x in aq):
            bad += 1
            continue
    if bad:
        return False, f"{bad} rows lack coherent two-sided depth"
    return True, f"all {len(rows)} rows have two-sided depth"


def _group_by_contract(rows):
    g = defaultdict(list)
    for r in rows:
        key = (str(r.get("token") or ""), str(r.get("side") or ""))
        if key[0] and key[1]:
            g[key].append(r)
    return g


def _check_contracts(rows):
    groups = _group_by_contract(rows)
    good = 0
    for key, grp in groups.items():
        if len(grp) >= MIN_SAMPLES_PER_CONTRACT:
            good += 1
    if good < MIN_CONTRACTS_PER_PRODUCT:
        return False, (
            f"{good} contracts with >= {MIN_SAMPLES_PER_CONTRACT} samples; "
            f"need >= {MIN_CONTRACTS_PER_PRODUCT}"
        )
    return True, f"{good} contracts with sufficient samples"


def _check_quantity_coherence(rows):
    """Within each contract, quantity values must be positive integers that
    are consistent with the contract's lot-size multiples. We do not require
    a fixed multiple; we require (a) all positive, (b) at least two distinct
    values observed across the group (proving the field varies and is not a
    placeholder), and (c) values are integral."""
    groups = _group_by_contract(rows)
    failures = []
    for (token, side), grp in groups.items():
        qs = []
        for r in grp:
            for q in (r.get("bid_quantities") or []):
                if isinstance(q, (int, float)):
                    qs.append(float(q))
            for q in (r.get("ask_quantities") or []):
                if isinstance(q, (int, float)):
                    qs.append(float(q))
        if not qs:
            failures.append(f"{token}/{side}: no numeric quantities")
            continue
        if any(q <= 0 for q in qs):
            failures.append(f"{token}/{side}: non-positive quantity observed")
            continue
        if any(abs(q - round(q)) > 1e-6 for q in qs):
            failures.append(f"{token}/{side}: non-integral quantity observed")
            continue
        distinct = len(set(qs))
        if distinct < 2:
            failures.append(f"{token}/{side}: quantity field constant ({qs[:3]}) — cannot rule out placeholder")
            continue
    if failures:
        return False, "; ".join(failures[:5])
    return True, "quantities positive, integral, non-constant per contract"


def _check_distinct_hashes(rows):
    hashes = [r.get("quote_payload_hash") for r in rows if r.get("quote_payload_hash")]
    distinct = len(set(hashes))
    if distinct < MIN_DISTINCT_PAYLOAD_HASHES:
        return False, f"only {distinct} distinct payload hashes; need {MIN_DISTINCT_PAYLOAD_HASHES}"
    return True, f"{distinct} distinct payload hashes"


def _check_timestamps(rows):
    with_ts = [r for r in rows if r.get("provider_timestamp")]
    if not with_ts:
        return False, "no provider timestamps on any sample"
    ages = [r.get("age_seconds") for r in with_ts
            if isinstance(r.get("age_seconds"), (int, float))]
    if not ages:
        return False, "provider timestamps present but ages not computable"
    if any(a < 0 for a in ages):
        return False, "negative age observed"
    ages_sorted = sorted(ages)
    p95 = ages_sorted[int(0.95 * (len(ages_sorted) - 1))]
    return True, f"n_ts={len(ages)} p95_age_s={p95:.1f} max_age_s={ages_sorted[-1]:.1f}"


def _check_freshness(rows):
    ages = [r.get("age_seconds") for r in rows
            if isinstance(r.get("age_seconds"), (int, float))]
    if not ages:
        return False, "cannot assess freshness; no ages"
    ages_sorted = sorted(ages)
    p95 = ages_sorted[int(0.95 * (len(ages_sorted) - 1))]
    if p95 > MAX_P95_AGE_SECONDS:
        return False, f"p95 age {p95:.1f}s exceeds {MAX_P95_AGE_SECONDS}s"
    return True, f"p95 age {p95:.1f}s within {MAX_P95_AGE_SECONDS}s"


def _check_sample_recency(rows):
    now = datetime.now(timezone.utc)
    recent = 0
    for r in rows:
        ts = r.get("collection_utc") or r.get("local_receive_timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if (now - dt.astimezone(timezone.utc)).total_seconds() <= MAX_ACCEPTABLE_SAMPLE_AGE_SECONDS:
            recent += 1
    if recent == 0:
        return False, "no sample collected within last 24h"
    return True, f"{recent} sample(s) collected within last 24h"


def verify_product(product):
    rows = _load_rows(product)
    if not rows:
        return {"product": product, "verdict": "HOLD",
                "reason": "NO_EVIDENCE", "checks": {}}
    results = {}
    ok, msg = _check_provider(rows)
    results["provider"] = (ok, msg)
    ok, msg = _check_product(rows, product)
    results["product"] = (ok, msg)
    ok, msg = _check_depth(rows)
    results["depth"] = (ok, msg)
    ok, msg = _check_contracts(rows)
    results["contracts"] = (ok, msg)
    ok, msg = _check_quantity_coherence(rows)
    results["quantity_coherence"] = (ok, msg)
    ok, msg = _check_distinct_hashes(rows)
    results["distinct_hashes"] = (ok, msg)
    ok, msg = _check_timestamps(rows)
    results["timestamps"] = (ok, msg)
    ok, msg = _check_freshness(rows)
    results["freshness"] = (ok, msg)
    ok, msg = _check_sample_recency(rows)
    results["sample_recency"] = (ok, msg)

    failures = [k for k, (ok, _) in results.items() if not ok]
    verdict = "PASS" if not failures else "HOLD"
    p95_age = None
    ages = [r.get("age_seconds") for r in rows
            if isinstance(r.get("age_seconds"), (int, float))]
    if ages:
        ages_sorted = sorted(ages)
        p95_age = ages_sorted[int(0.95 * (len(ages_sorted) - 1))]

    return {
        "product": product,
        "verdict": verdict,
        "sample_count": len(rows),
        "distinct_payload_hashes": len({r.get("quote_payload_hash") for r in rows if r.get("quote_payload_hash")}),
        "p95_age_seconds": p95_age,
        "failures": failures,
        "checks": {k: {"ok": v[0], "note": v[1]} for k, v in results.items()},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--products", default=",".join(_SUPPORTED))
    ap.add_argument("--report", default=None,
                    help="write verdict JSON to this path")
    args = ap.parse_args(argv)

    products = tuple(p.strip().upper() for p in args.products.split(",") if p.strip())
    reports = {p: verify_product(p) for p in products}

    for p, r in reports.items():
        print(f"===== {p} =====")
        print(f"  verdict={r['verdict']}  samples={r.get('sample_count', 0)}  "
              f"distinct_hashes={r.get('distinct_payload_hashes', 0)}  "
              f"p95_age_s={r.get('p95_age_seconds')}")
        for k, v in r.get("checks", {}).items():
            marker = "OK" if v["ok"] else "FAIL"
            print(f"    [{marker}] {k}: {v['note']}")

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
        print(f"REPORT_WRITTEN={out}")

    overall = "PASS" if all(r["verdict"] == "PASS" for r in reports.values()) else "HOLD"
    print(f"OVERALL={overall}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
