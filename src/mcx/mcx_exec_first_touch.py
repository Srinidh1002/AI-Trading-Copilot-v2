"""Section 7.21-7.23 — T1/SL ordering with sequence-aware tick stream."""
import os, sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _ts_iso(dt):
    if isinstance(dt, str):
        return dt
    return dt.astimezone(timezone.utc).isoformat()


class FirstTouchTracker:
    """Track T1/SL ordering for a long option using bid-side marks.
    Section 7.18: use executable bid (position side) as mark.
    """

    def __init__(self, t1_price, sl_price, min_interval_gap_seconds=None):
        self.t1_price = float(t1_price)
        self.sl_price = float(sl_price)
        self.t1_first_seen_at = None
        self.sl_first_seen_at = None
        self.t1_first_seen_quote_id = None
        self.sl_first_seen_quote_id = None
        self.t1_first_seen_exchange_time = None
        self.sl_first_seen_exchange_time = None
        self.t1_first_seen_sequence = None
        self.sl_first_seen_sequence = None
        self.last_ts = None
        self.last_seq = None
        self.last_quote_id = None
        self.min_interval_gap_seconds = min_interval_gap_seconds
        self.out_of_order_rejections = 0
        self.duplicate_rejections = 0
        self._last_seen_ts = None

    def ingest(self, bid_price, timestamp_iso, sequence_number=None, quote_id=None):
        """Feed one bid-side observation. Rejects stale / out-of-order ticks.
        Returns (action, note).
        """
        try:
            ts = datetime.fromisoformat(timestamp_iso)
        except Exception:
            return ("REJECTED", "TIMESTAMP_INVALID")
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # Out-of-order protection (Section 7.22)
        if self._last_seen_ts is not None and ts < self._last_seen_ts:
            self.out_of_order_rejections += 1
            return ("REJECTED", "OUT_OF_ORDER")
        if self._last_seen_ts is not None and ts == self._last_seen_ts:
            self.duplicate_rejections += 1
            return ("REJECTED", "DUPLICATE_TS")

        self._last_seen_ts = ts
        self.last_quote_id = quote_id
        if sequence_number is not None:
            self.last_seq = sequence_number

        if bid_price >= self.t1_price and self.t1_first_seen_at is None:
            self.t1_first_seen_at = _ts_iso(ts)
            self.t1_first_seen_quote_id = quote_id
            self.t1_first_seen_exchange_time = _ts_iso(ts)
            self.t1_first_seen_sequence = sequence_number
        if bid_price <= self.sl_price and self.sl_first_seen_at is None:
            self.sl_first_seen_at = _ts_iso(ts)
            self.sl_first_seen_quote_id = quote_id
            self.sl_first_seen_exchange_time = _ts_iso(ts)
            self.sl_first_seen_sequence = sequence_number

        if (self.t1_first_seen_at is not None and
            self.sl_first_seen_at is not None and
            self.t1_first_seen_at == self.sl_first_seen_at):
            return ("AMBIGUOUS", "BOTH_ON_SAME_TICK")
        return ("OK", None)

    def result(self):
        """Return first-touch result per Section 7.21."""
        t1 = self.t1_first_seen_at
        sl = self.sl_first_seen_at
        if t1 is None and sl is None:
            return "NEITHER"
        if t1 is not None and sl is None:
            return "T1_FIRST"
        if sl is not None and t1 is None:
            return "SL_FIRST"
        if t1 == sl:
            return "AMBIGUOUS"
        return "T1_FIRST" if t1 < sl else "SL_FIRST"

    def snapshot(self):
        return {
            "t1_price": self.t1_price,
            "sl_price": self.sl_price,
            "t1_first_seen_at": self.t1_first_seen_at,
            "sl_first_seen_at": self.sl_first_seen_at,
            "t1_first_seen_quote_id": self.t1_first_seen_quote_id,
            "sl_first_seen_quote_id": self.sl_first_seen_quote_id,
            "out_of_order_rejections": self.out_of_order_rejections,
            "duplicate_rejections": self.duplicate_rejections,
            "first_touch_result": self.result(),
            "t1_first_seen_exchange_time": self.t1_first_seen_exchange_time,
            "sl_first_seen_exchange_time": self.sl_first_seen_exchange_time,
            "t1_first_seen_sequence": self.t1_first_seen_sequence,
            "sl_first_seen_sequence": self.sl_first_seen_sequence,
            "last_processed_exchange_time": self._last_seen_ts.isoformat() if self._last_seen_ts else None,
            "last_processed_sequence": self.last_seq,
            "last_processed_quote_id": self.last_quote_id,
            "ambiguous_flag": self.result() == "AMBIGUOUS",
        }

    def to_state(self):
        """Serialize for atomic persistence in open position state."""
        return self.snapshot()

    @classmethod
    def from_state(cls, state):
        """Reconstruct exactly from persisted state. Preserves chronology."""
        t = cls(t1_price=state.get("t1_price", 0.0),
                sl_price=state.get("sl_price", 0.0))
        t.t1_first_seen_at = state.get("t1_first_seen_at")
        t.sl_first_seen_at = state.get("sl_first_seen_at")
        t.t1_first_seen_quote_id = state.get("t1_first_seen_quote_id")
        t.sl_first_seen_quote_id = state.get("sl_first_seen_quote_id")
        t.t1_first_seen_exchange_time = state.get("t1_first_seen_exchange_time")
        t.sl_first_seen_exchange_time = state.get("sl_first_seen_exchange_time")
        t.t1_first_seen_sequence = state.get("t1_first_seen_sequence")
        t.sl_first_seen_sequence = state.get("sl_first_seen_sequence")
        t.last_seq = state.get("last_processed_sequence")
        t.last_quote_id = state.get("last_processed_quote_id")
        # M7_first_touch_key_fix - read keys snapshot() actually writes;
        # fall back to legacy keys for old persisted state.
        t.out_of_order_rejections = int(
            state.get("out_of_order_rejections",
                      state.get("out_of_order_tick_count", 0)) or 0
        )
        t.duplicate_rejections = int(
            state.get("duplicate_rejections",
                      state.get("duplicate_tick_count", 0)) or 0
        )
        _lt = state.get("last_processed_exchange_time")
        if _lt:
            try:
                t._last_seen_ts = datetime.fromisoformat(_lt)
            except Exception:
                t._last_seen_ts = None
        return t


if __name__ == "__main__":
    t = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    print(t.ingest(100.0, "2026-09-12T10:00:00+00:00"))
    print(t.ingest(116.0, "2026-09-12T10:01:00+00:00"))
    print(t.ingest(90.0, "2026-09-12T10:02:00+00:00"))
    print("Result:", t.result())
    t2 = FirstTouchTracker(t1_price=115.0, sl_price=92.0)
    t2.ingest(100.0, "2026-09-12T10:00:00+00:00")
    t2.ingest(90.0, "2026-09-12T10:01:00+00:00")
    t2.ingest(116.0, "2026-09-12T10:02:00+00:00")
    print("SL first:", t2.result())
