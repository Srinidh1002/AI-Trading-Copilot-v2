"""Offline verifier for MCX FYERS execution calibration evidence (Option D).

Semantics:
  * Execution snapshot freshness = local observation age of a synchronous
    FYERS depth response. It is NOT a provider timestamp. Basis string:
    "SYNCHRONOUS_FYERS_DEPTH_RESPONSE".
  * Provider last-trade timestamp (from FYERS depth `ltt`) is informational
    liquidity evidence. It is not the freshness clock.
  * FYERS does not publish a per-snapshot depth-update timestamp; the
    collector reports depth_provider_timestamp_available accordingly.

Gates (all required):
  * provider == FYERS
  * supported product
  * two-sided depth with positive best bid/ask
  * coherent quantities (positive, integral, non-constant per contract)
  * CE + PE represented, single expiry
  * >= MIN_SAMPLES_PER_CONTRACT samples per contract
  * >= MIN_CONTRACTS_PER_PRODUCT contracts
  * >= MIN_DISTINCT_PAYLOAD_HASHES distinct depth payload hashes
  * session_status_at_collection == OPEN for every sample
  * bounded depth RTT: p95(depth_round_trip_ms) < MAX_P95_RTT_MS
  * bounded observation age: max(execution_snapshot_age_seconds) < MAX_SNAPSHOT_AGE_S
  * sample collected within last 24h

Reported but not gating:
  * depth_provider_timestamp_available
  * last_trade_age p95
  * last_trade_timestamp_source
  * quantity_semantics

Emits a machine-readable verdict dict. Exit 0 only on OVERALL=PASS.
Never writes config.
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
MAX_P95_RTT_MS = 10000.0
MAX_SNAPSHOT_AGE_S = 5.0
MAX_ACCEPTABLE_SAMPLE_AGE_SECONDS = 86400

_VERIFIED_QUANTITY_UNIT = "PROVIDER_QUANTITY"
_QUANTITY_UNIT_BASIS = (
    "FYERS depth level quantity. Provider documentation available in this "
    "repository does not establish the unit as exchange lots; recorded as "
    "provider quantity. Consumed only for relative liquidity and two-sided "
    "presence. Position sizing uses contract lot size, not this field."
)


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


def _positive(x):
    return isinstance(x, (int, float)) and x > 0


def _p95(values):
    if not values:
        return None
    vs = sorted(values)
    return vs[int(0.95 * (len(vs) - 1))]


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
        return False, f"multiple expiries: {sorted(expiries)}"
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


def _check_session_open(rows):
    bad = [
        (r.get("sample_ordinal"), r.get("session_status_at_collection"))
        for r in rows
        if str(r.get("session_status_at_collection") or "").upper() != "OPEN"
    ]
    if bad:
        return False, (
            f"{len(bad)} samples collected while session was not OPEN "
            f"(first: ordinal={bad[0][0]} status={bad[0][1]!r})"
        )
    return True, f"all {len(rows)} samples collected with session OPEN"


def _check_depth_rtt(rows):
    rtts = [
        r.get("depth_round_trip_ms")
        for r in rows
        if isinstance(r.get("depth_round_trip_ms"), (int, float))
    ]
    if not rtts:
        return False, "no depth_round_trip_ms recorded"
    p95 = _p95(rtts)
    if p95 > MAX_P95_RTT_MS:
        return False, f"p95 depth RTT {p95:.0f}ms exceeds {MAX_P95_RTT_MS:.0f}ms"
    return True, f"p95 rtt_ms={p95:.0f} (cap {MAX_P95_RTT_MS:.0f}ms)"


def _check_snapshot_age(rows):
    ages = [
        r.get("execution_snapshot_age_seconds")
        for r in rows
        if isinstance(r.get("execution_snapshot_age_seconds"), (int, float))
    ]
    if not ages:
        return False, "no execution_snapshot_age_seconds recorded"
    if any(a < 0 for a in ages):
        return False, "negative snapshot age observed"
    mx = max(ages)
    if mx > MAX_SNAPSHOT_AGE_S:
        return False, f"max observation age {mx:.3f}s exceeds {MAX_SNAPSHOT_AGE_S:.3f}s"
    return True, f"max observation age {mx:.3f}s (cap {MAX_SNAPSHOT_AGE_S:.3f}s)"


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
        ("session_open", lambda: _check_session_open(rows)),
        ("depth_rtt", lambda: _check_depth_rtt(rows)),
        ("snapshot_age", lambda: _check_snapshot_age(rows)),
        ("sample_recency", lambda: _check_sample_recency(rows)),
    ):
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"raised {type(exc).__name__}"
        results[name] = (ok, msg)

    failures = [k for k, (ok, _) in results.items() if not ok]
    verdict = "PASS" if not failures else "HOLD"

    # --- evidence-derived summaries ---
    rtts = [
        r.get("depth_round_trip_ms")
        for r in rows
        if isinstance(r.get("depth_round_trip_ms"), (int, float))
    ]
    lt_ages = [
        r.get("last_trade_age_seconds")
        for r in rows
        if isinstance(r.get("last_trade_age_seconds"), (int, float))
    ]
    snap_ages = [
        r.get("execution_snapshot_age_seconds")
        for r in rows
        if isinstance(r.get("execution_snapshot_age_seconds"), (int, float))
    ]
    lt_sources = sorted({str(r.get("last_trade_timestamp_source") or "UNAVAILABLE") for r in rows})
    provider_depth_ts_available = (
        all(bool(r.get("depth_provider_timestamp_available")) for r in rows) if rows else False
    )

    p95_rtt = _p95(rtts)
    p95_lt_age = _p95(lt_ages)
    max_snap_age = max(snap_ages) if snap_ages else None

    out = {
        "product": product,
        "verdict": verdict,
        "sample_count": len(rows),
        "distinct_payload_hashes": len(
            {r.get("quote_payload_hash") for r in rows if r.get("quote_payload_hash")}
        ),
        "deprecated_freshness_fields": [],
        "failures": failures,
        "checks": {k: {"ok": v[0], "note": v[1]} for k, v in results.items()},
        "reported": {
            "DEPTH_SAMPLES": len(rows),
            "DISTINCT_DEPTH_HASHES": len(
                {r.get("quote_payload_hash") for r in rows if r.get("quote_payload_hash")}
            ),
            "DEPTH_TWO_SIDED": all(
                bool(r.get("bid_levels")) and bool(r.get("ask_levels")) for r in rows
            ),
            "DEPTH_RTT_P95_MS": p95_rtt,
            "DEPTH_OBSERVATION_FRESHNESS": (
                f"max_snapshot_age_s={max_snap_age:.3f}" if max_snap_age is not None else None
            ),
            "PROVIDER_DEPTH_TIMESTAMP_AVAILABLE": provider_depth_ts_available,
            "LAST_TRADE_AGE_P95": p95_lt_age,
            "LAST_TRADE_TIMESTAMP_SOURCE": lt_sources,
            "QUANTITY_SEMANTICS": _VERIFIED_QUANTITY_UNIT,
        },
        "depth_freshness_basis": "SYNCHRONOUS_FYERS_DEPTH_RESPONSE",
        "last_trade_recency_basis": (lt_sources[0] if len(lt_sources) == 1 else lt_sources),
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
            f"distinct_hashes={r.get('distinct_payload_hashes', 0)}"
        )
        for k, v in r.get("checks", {}).items():
            marker = "OK" if v["ok"] else "FAIL"
            print(f"    [{marker}] {k}: {v['note']}")
        reported = r.get("reported") or {}
        if reported:
            print("  -- reported --")
            for k, v in reported.items():
                print(f"    {k} = {v}")

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
