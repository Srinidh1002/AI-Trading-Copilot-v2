"""MCX instrument identity resolver.
Reads Angel One instrument master (data/instruments.json). No broker calls.
"""
import json
import os
import sys
from datetime import date, datetime
from typing import Optional

# Allow running this file directly: python src/mcx/mcx_identity.py
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_contracts import ANGEL_MASTER_SCALE, PRODUCTS


def _parse_expiry(raw: str) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%d%b%Y", "%d%b%y"):
        try:
            return datetime.strptime(str(raw).upper(), fmt).date()
        except Exception:
            continue
    return None


class MCXIdentityResolver:
    def __init__(self, master_path: str = "data/instruments.json"):
        with open(master_path, encoding="utf-8") as f:
            self.master = json.load(f)
        self._mcx = [r for r in self.master if str(r.get("exch_seg", "")).upper() == "MCX"]

    def futures(self, product: str) -> list:
        spec = PRODUCTS.get(product.upper())
        if not spec:
            return []
        rows = [
            r for r in self._mcx
            if r.get("instrumenttype") == spec["future_instr_type"]
            and str(r.get("name", "")).upper() == product.upper()
        ]
        rows.sort(key=lambda r: _parse_expiry(r.get("expiry")) or date.max)
        return rows

    def option_expiries(self, product: str) -> list:
        spec = PRODUCTS.get(product.upper())
        if not spec:
            return []
        seen = set()
        for r in self._mcx:
            if (r.get("instrumenttype") == spec["option_instr_type"]
                and str(r.get("name", "")).upper() == product.upper()):
                d = _parse_expiry(r.get("expiry"))
                if d:
                    seen.add(d)
        return sorted(seen)

    def options(self, product: str, expiry: date) -> list:
        spec = PRODUCTS.get(product.upper())
        if not spec:
            return []
        exp_str = expiry.strftime("%d%b%Y").upper()
        return [
            r for r in self._mcx
            if r.get("instrumenttype") == spec["option_instr_type"]
            and str(r.get("name", "")).upper() == product.upper()
            and str(r.get("expiry", "")).upper() == exp_str
        ]

    def resolve_active(self, product: str, as_of: Optional[date] = None) -> dict:
        if as_of is None:
            as_of = date.today()

        futs = self.futures(product)
        active_fut = next(
            (f for f in futs if (_parse_expiry(f.get("expiry")) or date.min) >= as_of),
            None
        )

        opt_exps = self.option_expiries(product)
        active_opt_exp = next((e for e in opt_exps if e >= as_of), None)

        result = {
            "product": product.upper(),
            "as_of": as_of.isoformat(),
            "futures": active_fut,
            "option_expiry": active_opt_exp.isoformat() if active_opt_exp else None,
            "calls": {},
            "puts": {},
            "status": "OK",
        }

        if active_fut is None or active_opt_exp is None:
            result["status"] = "EVIDENCE_UNAVAILABLE_IDENTITY"
            return result

        for r in self.options(product, active_opt_exp):
            sym = str(r.get("symbol", "")).upper()
            raw_strike = float(r.get("strike", 0) or 0)
            strike = raw_strike / ANGEL_MASTER_SCALE if raw_strike else None
            if strike is None:
                continue
            if sym.endswith("CE"):
                result["calls"][strike] = r
            elif sym.endswith("PE"):
                result["puts"][strike] = r

        return result


if __name__ == "__main__":
    r = MCXIdentityResolver()
    out = r.resolve_active("CRUDEOILM")
    print(f"status={out['status']}")
    print(f"futures={out['futures']['symbol'] if out['futures'] else None}")
    print(f"option_expiry={out['option_expiry']}")
    print(f"calls={len(out['calls'])} strikes, puts={len(out['puts'])} strikes")
