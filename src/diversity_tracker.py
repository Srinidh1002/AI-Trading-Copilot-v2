"""Equity certification diversity tracker - neutral, market-agnostic.

Tracks daily/regime/phase diversity of countable certification trades
for a single market. Independent per NIFTY / SENSEX instance.

Per the certification contract:
  >= 5 distinct trading days
  >= 2 distinct regimes
  >= 2 distinct session phases
  <= 40 countable certification trades per trading day

Not imported by MCX. Equity-only.
"""
DIVERSITY_MIN_DAYS    = 5
DIVERSITY_MIN_REGIMES = 2
DIVERSITY_MIN_PHASES  = 2
DIVERSITY_MAX_PER_DAY = 40


class EquityCertificationDiversityTracker:
    """Per-market diversity state for the certification denominator."""

    def __init__(self):
        self.trading_dates   = set()
        self.regimes         = set()
        self.session_phases  = set()
        self.countable_by_day = {}

    def would_count(self, trade_date, regime, phase):
        """Return (countable: bool, reason: str|None). Does NOT mutate state."""
        if not trade_date:
            return False, "MISSING_TRADE_DATE"
        day_count = int(self.countable_by_day.get(trade_date, 0) or 0)
        if day_count >= DIVERSITY_MAX_PER_DAY:
            return False, "DAILY_DIVERSITY_CAP_REACHED"
        return True, None

    def record(self, trade_date, regime, phase):
        """Add diversity contribution for one countable trade.
        Caller must ensure idempotency (bot uses counted_trade_ids).
        """
        if not trade_date:
            return
        self.trading_dates.add(trade_date)
        if regime:
            self.regimes.add(regime)
        if phase:
            self.session_phases.add(phase)
        self.countable_by_day[trade_date] = int(self.countable_by_day.get(trade_date, 0) or 0) + 1

    def evaluate(self):
        """Return (ok: bool, details: dict). Sample validity check."""
        days    = len(self.trading_dates)
        regimes = len(self.regimes)
        phases  = len(self.session_phases)
        max_per_day = max(self.countable_by_day.values()) if self.countable_by_day else 0
        ok = (
            days    >= DIVERSITY_MIN_DAYS
            and regimes >= DIVERSITY_MIN_REGIMES
            and phases  >= DIVERSITY_MIN_PHASES
            and max_per_day <= DIVERSITY_MAX_PER_DAY
        )
        return ok, {
            "diversity_days":        days,
            "diversity_regimes":     regimes,
            "diversity_phases":      phases,
            "max_countable_per_day": max_per_day,
        }

    def to_state(self):
        return {
            "trading_dates":    sorted(self.trading_dates),
            "regimes":          sorted(self.regimes),
            "session_phases":   sorted(self.session_phases),
            "countable_by_day": dict(self.countable_by_day),
        }

    @classmethod
    def from_state(cls, state):
        t = cls()
        if not state:
            return t
        t.trading_dates  = set(state.get("trading_dates") or [])
        t.regimes        = set(state.get("regimes") or [])
        t.session_phases = set(state.get("session_phases") or [])
        cbd = state.get("countable_by_day") or {}
        t.countable_by_day = {str(k): int(v or 0) for k, v in cbd.items()}
        return t


if __name__ == "__main__":
    print("diversity_tracker module loaded OK")
    t = EquityCertificationDiversityTracker()
    print("would_count fresh:", t.would_count("2026-09-16", "CONTINUOUS", "TRENDING_UP"))
    t.record("2026-09-16", "CONTINUOUS", "TRENDING_UP")
    print("after 1 record:", t.to_state())
    print("evaluate:", t.evaluate())
