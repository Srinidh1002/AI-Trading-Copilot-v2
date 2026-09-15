"""Price + OI classification — spec §10.
PRICE↑+OI↑ = LONG_BUILDUP
PRICE↓+OI↑ = SHORT_BUILDUP
PRICE↑+OI↓ = SHORT_COVERING
PRICE↓+OI↓ = LONG_UNWINDING
"""


class PriceOITracker:
    def __init__(self):
        self._prev = None  # {price, oi, ts}

    def update(self, price, oi):
        """Call once per cycle with current future price and OI."""
        state = "UNKNOWN"
        price_chg_pct = None
        oi_chg_pct = None

        if self._prev is not None and self._prev["price"] > 0 and self._prev["oi"] > 0:
            price_chg_pct = (price - self._prev["price"]) / self._prev["price"] * 100
            oi_chg_pct = (oi - self._prev["oi"]) / self._prev["oi"] * 100

            price_up = price_chg_pct > 0.01
            price_dn = price_chg_pct < -0.01
            oi_up = oi_chg_pct > 0.1
            oi_dn = oi_chg_pct < -0.1

            if price_up and oi_up:   state = "LONG_BUILDUP"
            elif price_dn and oi_up: state = "SHORT_BUILDUP"
            elif price_up and oi_dn: state = "SHORT_COVERING"
            elif price_dn and oi_dn: state = "LONG_UNWINDING"
            else:                    state = "FLAT"

        self._prev = {"price": price, "oi": oi}

        # Reason string for audit
        if price_chg_pct is None:
            reason = "BASELINE_UNAVAILABLE"
        elif state == "FLAT":
            reason = f"BOTH_BELOW_THRESHOLD(p<0.10%,oi<0.10%)"
        else:
            reason = f"CLASSIFIED_{state}"

        return {
            "state": state,
            "reason": reason,
            "price_chg_pct": round(price_chg_pct, 3) if price_chg_pct is not None else None,
            "oi_chg_pct": round(oi_chg_pct, 3) if oi_chg_pct is not None else None,
            "price": price,
            "oi": oi,
        }


def score(state):
    """Map classification to directional score (-30..+30)."""
    m = {
        "LONG_BUILDUP": +30,
        "SHORT_COVERING": +10,
        "SHORT_BUILDUP": -30,
        "LONG_UNWINDING": -10,
        "FLAT": 0,
        "UNKNOWN": 0,
    }
    return m.get(state, 0)


if __name__ == "__main__":
    t = PriceOITracker()
    print(t.update(9500, 500000))
    print(t.update(9510, 510000))  # LONG_BUILDUP
    print(t.update(9490, 520000))  # SHORT_BUILDUP
    print(t.update(9500, 500000))  # LONG_UNWINDING (price up OI down)
