"""F8 - FYERS public symbol-master fetch. DATA ONLY.

Fetches FYERS public symbol masters into the F8 store. No auth, no
order APIs. The operator must ensure network access to the FYERS
public data host. Never prints tokens or credentials.

If the default URL layout does not match your environment, override
SEGMENT_URLS below.
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request

from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterStoreV2,
    SUPPORTED_SEGMENTS,
)

# Default FYERS public master URL pattern. Segment slug = the segment
# name used by FYERS. Adjust if your FYERS account exposes a different
# public host.
SEGMENT_URLS = {
    "NSE_CM":     "https://public.fyers.in/sym_details/NSE_CM.csv",
    "NSE_FO":     "https://public.fyers.in/sym_details/NSE_FO.csv",
    "BSE_CM":     "https://public.fyers.in/sym_details/BSE_CM.csv",
    "BSE_FO":     "https://public.fyers.in/sym_details/BSE_FO.csv",
    "MCX_COM":    "https://public.fyers.in/sym_details/MCX_COM.csv",
}


def fetch_csv(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "AI-Trading-Copilot-F8/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    # FYERS masters are typically ascii with occasional non-utf8 bytes
    return raw.decode("utf-8", errors="replace")


def _unix_to_iso_date(ts):
    """Unix seconds (int/str) -> YYYY-MM-DD; '' on failure."""
    if not ts:
        return ""
    try:
        n = int(ts)
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    # FYERS uses midnight-IST-of-trading-day as the timestamp; taking
    # UTC date can roll back a day, so compute IST date instead.
    from datetime import datetime, timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.fromtimestamp(n, tz=ist).date().isoformat()


def _exchange_code_to_name(code):
    return {"10": "NSE", "11": "MCX", "12": "BSE"}.get(str(code), None)


def parse_csv_rows(text: str) -> list[dict]:
    """FYERS public master CSV: comma-delimited, 21 fields per row.

    Real schema (verified against public.fyers.in on 2026-09-17):
      0  fyToken                11 segment_code
      1  description            12 token_numeric
      2  type_code              13 underlying_root
      3  lot_size               14 strike_or_ref
      4  tick_size              15 const (-1.0)
      5  isin                   16 optType (XX | CE | PE | blank)
      6  session_times (has |)  17 underlying_fyToken
      7  last_update_date       18 expiry_unix_repeat
      8  expiry_unix ('' cash)  19 flag
      9  symbol                 20 flag
    """
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        # session_times field embeds a '|', but no field contains ','
        # beyond the outer delimiter, so plain split(',') is safe.
        p = line.split(",")
        if len(p) < 18:
            continue
        row = {
            "fyToken":           p[0].strip(),
            "description":       p[1].strip(),
            "type_code":         p[2].strip(),
            "lot_size":          p[3].strip(),
            "tick_size":         p[4].strip(),
            "isin":              p[5].strip(),
            "session_times":     p[6].strip(),
            "last_update_date":  p[7].strip(),
            "expiry":            _unix_to_iso_date(p[8]),
            "symbol":            p[9].strip(),
            "exch":              _exchange_code_to_name(p[10]) or "",
            "segment_code":      p[11].strip(),
            "token_numeric":     p[12].strip(),
            "underlying_symbol": p[13].strip(),
            # Field 14 = underlying reference (spot-ish), not strike.
            # Field 15 = real strike (negative or -1.0 for non-options).
            "underlying_reference": p[14].strip(),
            "strike":            p[15].strip(),
            "optType":           p[16].strip(),
            "underlying_fyToken":p[17].strip(),
        }
        rows.append(row)
    return rows


def main() -> int:
    store = FyersSymbolMasterStoreV2()
    for seg in SUPPORTED_SEGMENTS:
        url = SEGMENT_URLS.get(seg)
        if not url:
            print(f"  [skip] no URL configured for {seg}")
            continue
        print(f"  fetching {seg} from {url} ...", flush=True)
        try:
            text = fetch_csv(url)
        except Exception as exc:
            print(f"  [error] {seg}: {type(exc).__name__}: {exc}")
            return 1
        rows = parse_csv_rows(text)
        if not rows:
            print(f"  [error] {seg}: master has no rows")
            return 1
        store.save(seg, rows)
        print(f"  [ok] {seg}: {len(rows)} rows cached")
    print()
    print("MASTER_FETCH=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
