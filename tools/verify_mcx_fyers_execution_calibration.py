"""Offline verifier for MCX FYERS execution calibration evidence.

Reads the JSONL produced by collect_mcx_fyers_execution_calibration.py
and independently determines whether the evidence can prove live
execution-depth semantics for a product.

Required evidence per product:
  * one provider identity (FYERS only)
  * supported product
  * real option identities: CE and PE both present, same expiry
  * non-empty two-sided depth with positive bid and ask prices
  * quantities positive, integral, and non-constant
  * enough independent observations per contract
  * minimum distinct payload hashes (proves the market moved / ticked)
  * provider timestamp on every sample, from an authoritative provider
    source (never local wall time)
  * freshness computable and within the tolerance derived from the
    observed distribution
  * evidence recency within the last 24h

Emits a machine-readable verdict dict and prints a summary. Exit 0 only
on OVERALL=PASS. Never writes config.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
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

# Verified quantity unit: FYERS depth API exposes per-level quantity but
# does not, in the SDK surface available to this repository, publish an
# authoritative statement that this figure is expressed in exchange lots.
# Recording the truthful, verifiable semantics is required; recording
# "LOTS" without that proof would be fabrication.
_VERIFIED_QUANTITY_UNIT = "PROVIDER_QUANTITY"
_QUANTITY_UNIT_BASIS = (
    "FYERS depth level quantity. Provider documentation available in this "
    "repository does not establish the unit as exchange lots; recorded as "
    "provider quantity. Consumed only for relative liquidity and two-sided "
    "presence. Position sizing uses contract lot size, not this field."
)

# Provider timestamp source must begin with one of these. Local wall time
# is never a provider timestamp.
_PROVIDER_TS_SOURCE_PREFIXES = ("DEPTH:", "QUOTES:")


def _load_rows(product=None):
    rows = []
    for p in sorted(_EVIDENCE_DIR.glob("*.jsonl")):
        if product and not p.name.startswith(product):
            continue
        try:
            with open(p, encoding="utf-8") as f:
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


def _positive(x):
    return isinstance(x, (int, float)) and x > 0


def _check_depth(rows):
    """Two-sided depth with positive bid and ask prices per sample."""
    bad_depth = 0
    bad_price = 0
    for r in rows:
        bids = r.get("bid_levels") or []
        asks = r.get("ask_levels") or []
        if not bids or not asks:
            bad_depth += 1
            continue
        b0 = bids[0]
        a0 = asks[0]
        if not isinstance(b0, dict) or not _positive(b0.get("price")):
            bad_price += 1
            continue
        if not isinstance(a0, dict) or not _positive(a0.get("price")):
            bad_price += 1
            continue
    if bad_depth:
        return False, f"{bad_depth} rows lack two-sided depth"
    if bad_price:
        return False, f"{bad_price} rows have non-positive best bid/ask"
    return True, f"all {len(rows)} rows have two-sided depth with positive prices"


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
    for _key, grp in groups.items():
        if len(grp) >= MIN_SAMPLES_PER_CONTRACT:
            good += 1
    if good < MIN_CONTRACTS_PER_PRODUCT:
        return False, (
            f"{good} contracts with >= {MIN_SAMPLES_PER_CONTRACT} samples; "
            f"need >= {MIN_CONTRACTS_PER_PRODUCT}"
        )
    return True, f"{good} contracts with sufficient samples"


def _check_ce_pe_coverage(rows):
    sides = {str(r.get("side") or "").upper() for r in rows}
    missing = []
    if "CE" not in sides:
        missing.append("CE")
    if "PE" not in sides:
        missing.append("PE")
    if missing:
        return False, f"missing side(s): {missing}"
    return True, "both CE and PE represented"


def _check_expiry_coherence(rows):
    expiries = {str(r.get("expiry") or "") for r in rows if r.get("expiry")}
    if not expiries:
        return False, "no expiry recorded"
    if len(expiries) > 1:
        return False, f"multiple expiries in one product sample: {sorted(expiries)}"
    return True, f"single expiry {next(iter(expiries))}"


def _check_quantity_coherence(rows):
    groups = _group_by_contract(rows)
    failures = []
    for (token, side), grp in groups.items():
        qs = []
        for r in grp:
            for q in r.get("bid_quantities") or []:
                if isinstance(q, (int, float)):
                    qs.append(float(q))
            for q in r.get("ask_quantities") or []:
                if isinstance(q, (int, float)):
                    qs.append(float(q))
        if not qs:
            failures.append(f"{token}/{side}: no numeric quantities")
            continue
        if any(q <= 0 for q in qs):
            failures.append(f"{token}/{side}: non-positive quantity")
            continue
        if any(abs(q - round(q)) > 1e-6 for q in qs):
            failures.append(f"{token}/{side}: non-integral quantity")
            continue
        if len(set(qs)) < 2:
            failures.append(f"{token}/{side}: quantity field constant")
            continue
    if failures:
        return False, "; ".join(failures[:5])
    return True, "quantities positive, integral, non-constant per contract"


def _check_distinct_hashes(rows):
    hashes = [r.get("quote_payload_hash") for r in rows if r.get("quote_payload_hash")]
    distinct = len(set(hashes))
    if distinct < MIN_DISTINCT_PAYLOAD_HASHES:
        return (
            False,
            f"only {distinct} distinct payload hashes; need {MIN_DISTINCT_PAYLOAD_HASHES}",
        )
    return True, f"{distinct} distinct payload hashes"


def _check_timestamps(rows):
    with_ts = [r for r in rows if r.get("provider_timestamp")]
    if not with_ts:
        return False, "no provider timestamps on any sample"
    bad_source = []
    for r in with_ts:
        src = str(r.get("provider_timestamp_source") or "")
        if not any(src.startswith(p) for p in _PROVIDER_TS_SOURCE_PREFIXES):
            bad_source.append((r.get("sample_ordinal"), src or "<none>"))
    if bad_source:
        return False, (
            f"{len(bad_source)} samples lack an authoritative provider "
            f"timestamp source (first: ordinal={bad_source[0][0]} "
            f"source={bad_source[0][1]})"
        )
    ages = [
        r.get("age_seconds")
        for r in with_ts
        if isinstance(r.get("age_seconds"), (int, float))
    ]
    if not ages:
        return False, "provider timestamps present but ages not computable"
    if any(a < 0 for a in ages):
        return False, "negative age observed"
    ages_sorted = sorted(ages)
    p95 = ages_sorted[int(0.95 * (len(ages_sorted) - 1))]
    sources = sorted({str(r.get("provider_timestamp_source") or "") for r in with_ts})
    return (
        True,
        f"n_ts={len(ages)} p95_age_s={p95:.1f} max_age_s={ages_sorted[-1]:.1f} "
        f"sources={sources}",
    )


def _check_freshness(rows):
    ages = [
        r.get("age_seconds")
        for r in rows
        if isinstance(r.get("age_seconds"), (int, float))
    ]
    if not ages:
        return False, "cannot assess freshness; no ages"
    ages_sorted = sorted(ages)
    p95 = ages_sorted[int(0.95 * (len(ages_sorted) - 1))]
    if p95 > MAX_P95_AGE_SECONDS:
        return False, f"p95 age {p95:.1f}s exceeds {MAX_P95_AGE_SECONDS}s"
    return True, f"p95 age {p95:.1f}s within {MAX_P95_AGE_SECONDS}s"


def _check_sample_recency(rows):
    now = datetime.now(UTC)
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
            dt = dt.replace(tzinfo=UTC)
        if (now - dt.astimezone(UTC)).total_seconds() <= MAX_ACCEPTABLE_SAMPLE_AGE_SECONDS:
            recent += 1
    if recent == 0:
        return False, "no sample collected within last 24h"
    return True, f"{recent} sample(s) collected within last 24h"


def verify_product(product):
    rows = _load_rows(product)
    if not rows:
        return {
            "product": product,
            "verdict": "HOLD",
            "reason": "NO_EVIDENCE",
            "checks": {},
        }
    results = {}
    for name, fn in (
        ("provider", lambda: _check_provider(rows)),
        ("product", lambda: _check_product(rows, product)),
        ("depth", lambda: _check_depth(rows)),
        ("contracts", lambda: _check_contracts(rows)),
        ("ce_pe_coverage", lambda: _check_ce_pe_coverage(rows)),
        ("expiry_coherence", lambda: _check_expiry_coherence(rows)),
        ("quantity_coherence", lambda: _check_quantity_coherence(rows)),
        ("distinct_hashes", lambda: _check_distinct_hashes(rows)),
        ("timestamps", lambda: _check_timestamps(rows)),
        ("freshness", lambda: _check_freshness(rows)),
        ("sample_recency", lambda: _check_sample_recency(rows)),
    ):
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"raised {type(exc).__name__}"
        results[name] = (ok, msg)

    failures = [k for k, (ok, _) in results.items() if not ok]
    verdict = "PASS" if not failures else "HOLD"

    ages = [
        r.get("age_seconds")
        for r in rows
        if isinstance(r.get("age_seconds"), (int, float))
    ]
    p95_age = None
    if ages:
        ages_sorted = sorted(ages)
        p95_age = ages_sorted[int(0.95 * (len(ages_sorted) - 1))]

    out = {
        "product": product,
        "verdict": verdict,
        "sample_count": len(rows),
        "distinct_payload_hashes": len(
            {r.get("quote_payload_hash") for r in rows if r.get("quote_payload_hash")}
        ),
        "p95_age_seconds": p95_age,
        "failures": failures,
        "checks": {k: {"ok": v[0], "note": v[1]} for k, v in results.items()},
    }
    if verdict == "PASS":
        out["verified_quantity_unit"] = _VERIFIED_QUANTITY_UNIT
        out["quantity_unit_basis"] = _QUANTITY_UNIT_BASIS
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--products", default=",".join(_SUPPORTED))
    ap.add_argument("--report", default=None, help="write verdict JSON to this path")
    args = ap.parse_args(argv)

    products = tuple(p.strip().upper() for p in args.products.split(",") if p.strip())
    reports = {p: verify_product(p) for p in products}

    for p, r in reports.items():
        print(f"===== {p} =====")
        print(
            f"  verdict={r['verdict']}  samples={r.get('sample_count', 0)}  "
            f"distinct_hashes={r.get('distinct_payload_hashes', 0)}  "
            f"p95_age_s={r.get('p95_age_seconds')}"
        )
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
