"""Stable PCR metrics — spec §2.
Fixes the ATM-migration instability by using a FIXED strike universe
around a REFERENCE strike that only updates on large spot moves.
Also computes PCR change rate + EMA smoothing.
"""
import time


REFERENCE_REFRESH_PCT = 1.0   # refresh reference if spot moves >1%
UNIVERSE_STEPS = 10           # ±10 strikes around reference
PCR_EMA_ALPHA = 0.5           # 3-period EMA equivalent


class StablePCR:
    def __init__(self, strike_step=50, epoch="POST_PRECISION_V2"):
        self.strike_step = strike_step
        self.epoch = epoch
        self.reference_strike = None
        self._pcr_history = []
        self._prev_call_oi = None
        self._prev_put_oi = None

    def reset(self, new_epoch=None):
        """Clear PCR history (certification epoch change)."""
        if new_epoch:
            self.epoch = new_epoch
        self._pcr_history = []
        self._prev_call_oi = None
        self._prev_put_oi = None

    def _build_universe(self, ref):
        step = self.strike_step
        return [ref + i * step for i in range(-UNIVERSE_STEPS, UNIVERSE_STEPS + 1)]

    def compute(self, chain):
        """chain: dict from build_chain with ce_data/pe_data/future_ltp/atm."""
        if not chain or chain.get("status") != "OK":
            return {"status": "EVIDENCE_UNAVAILABLE"}

        fut = chain.get("future_ltp")
        if not fut:
            return {"status": "NO_FUTURE_LTP"}

        # Refresh reference only if spot moved > REFERENCE_REFRESH_PCT
        if self.reference_strike is None:
            self.reference_strike = round(fut / self.strike_step) * self.strike_step
        else:
            drift_pct = abs(fut - self.reference_strike) / self.reference_strike * 100
            if drift_pct >= REFERENCE_REFRESH_PCT:
                self.reference_strike = round(fut / self.strike_step) * self.strike_step
                # Reset OI history on reference change (avoid comparing across windows)
                self._prev_call_oi = None
                self._prev_put_oi = None

        universe = self._build_universe(self.reference_strike)
        ce = chain.get("ce_data", {})
        pe = chain.get("pe_data", {})

        total_call_oi = 0
        total_put_oi = 0
        total_call_vol = 0
        total_put_vol = 0
        contracts_used = 0

        for s in universe:
            c = ce.get(s)
            p = pe.get(s)
            if c:
                total_call_oi += c.get("oi", 0)
                total_call_vol += c.get("vol", 0)
                contracts_used += 1
            if p:
                total_put_oi += p.get("oi", 0)
                total_put_vol += p.get("vol", 0)
                contracts_used += 1

        pcr_oi = round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else None
        pcr_vol = round(total_put_vol / total_call_vol, 4) if total_call_vol > 0 else None

        # Change in OI (spec §2 requires call_change_oi / put_change_oi)
        call_change = (total_call_oi - self._prev_call_oi) if self._prev_call_oi is not None else 0
        put_change = (total_put_oi - self._prev_put_oi) if self._prev_put_oi is not None else 0
        self._prev_call_oi = total_call_oi
        self._prev_put_oi = total_put_oi

        # Coverage: universe is N strikes; each strike may have CE + PE = 2N contracts.
        # Require >= 80% of max contracts (e.g. 42 -> require >= 33).
        max_contracts = len(universe) * 2
        min_required = int(max_contracts * 0.8)
        if contracts_used < min_required:
            return {
                "status": "PCR_INCOMPLETE",
                "reason": f"CHAIN_COVERAGE_{contracts_used}/{max_contracts} (need {min_required})",
                "reference_strike": self.reference_strike,
                "universe_strikes": len(universe),
                "max_contracts": max_contracts,
                "contracts_used": contracts_used,
                "missing_strikes": [s for s in universe if s not in ce and s not in pe],
            }

        # EMA-3 smoothing of PCR
        self._pcr_history.append(pcr_oi)
        if len(self._pcr_history) > 6:
            self._pcr_history = self._pcr_history[-6:]
        pcr_ema = None
        if self._pcr_history:
            ema = self._pcr_history[0]
            for v in self._pcr_history[1:]:
                if v is not None:
                    ema = PCR_EMA_ALPHA * v + (1 - PCR_EMA_ALPHA) * ema
            pcr_ema = round(ema, 4)

        pcr_change_rate = None
        if len(self._pcr_history) >= 2:
            last = self._pcr_history[-1]
            prev = self._pcr_history[-2]
            if last is not None and prev is not None and prev != 0:
                pcr_change_rate = round((last - prev) / prev * 100, 3)

        return {
            "status": "OK",
            "epoch": self.epoch,
            "reference_strike": self.reference_strike,
            "universe_strikes": len(universe),
            "max_contracts": len(universe) * 2,
            "contracts_used": contracts_used,
            "strike_universe": universe,
            "ce_total_oi": total_call_oi,
            "pe_total_oi": total_put_oi,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "total_call_vol": total_call_vol,
            "total_put_vol": total_put_vol,
            "call_change_oi": call_change,
            "put_change_oi": put_change,
            "PCR_TOTAL_OI": pcr_oi,
            "PCR_VOLUME": pcr_vol,
            "PCR_EMA_3": pcr_ema,
            "PCR_CHANGE_RATE": pcr_change_rate,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }


if __name__ == "__main__":
    sp = StablePCR(strike_step=50)
    print("StablePCR module loaded OK")
