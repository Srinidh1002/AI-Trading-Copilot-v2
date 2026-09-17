"""Equity first-touch tracker - neutral, market-agnostic.

Tracks chronological ordering of T1 / SL crossings using executable bid
observations for long options positions. Equity-only. No MCX imports.

Semantics:
    T1 crossing: bid >= t1_price
    SL crossing: bid <= sl_price
    Result is set once and never flips.

Persistable via to_state / from_state. Safe against restart.
"""
from datetime import datetime


NONE       = "NONE"
T1_FIRST   = "T1_FIRST"
SL_FIRST   = "SL_FIRST"
AMBIGUOUS  = "AMBIGUOUS"


class EquityFirstTouchTracker:

    def __init__(self, t1_price, t2_price=None, t3_price=None, sl_price=None):
        self.t1_price = float(t1_price) if t1_price else None
        self.t2_price = float(t2_price) if t2_price else None
        self.t3_price = float(t3_price) if t3_price else None
        self.sl_price = float(sl_price) if sl_price else None

        self.t1_hit = False
        self.t2_hit = False
        self.t3_hit = False
        self.sl_hit = False

        self.t1_first_seen_at   = None
        self.sl_first_seen_at   = None
        self.t2_first_seen_at   = None
        self.t3_first_seen_at   = None

        self.t1_bid = None
        self.sl_bid = None
        self.t2_bid = None
        self.t3_bid = None

        self.t1_quote_time = None
        self.sl_quote_time = None

        self.t1_quote_id = None
        self.sl_quote_id = None

        self.last_valid_bid        = None
        self.last_valid_quote_time = None

        self.first_touch_sequence = 0
        self._result = NONE

    def result(self):
        return self._result

    def ingest_bid(self, bid, timestamp_iso, quote_id=None, exchange_time=None):
        """Feed one executable bid observation.
        Returns dict summary of what happened this call.
        """
        outcome = {"accepted": False, "reason": None,
                   "t1_crossed_now": False, "t2_crossed_now": False,
                   "t3_crossed_now": False, "sl_crossed_now": False,
                   "result": self._result}

        if bid is None:
            outcome["reason"] = "NO_BID"
            return outcome
        try:
            bid = float(bid)
        except (TypeError, ValueError):
            outcome["reason"] = "BAD_BID"
            return outcome
        if bid <= 0:
            outcome["reason"] = "NON_POSITIVE_BID"
            return outcome
        if not timestamp_iso:
            outcome["reason"] = "NO_TIMESTAMP"
            return outcome

        # accept observation
        self.first_touch_sequence += 1
        self.last_valid_bid        = bid
        self.last_valid_quote_time = timestamp_iso
        outcome["accepted"] = True

        # per-milestone first-time crossings
        if self.t1_price is not None and not self.t1_hit and bid >= self.t1_price:
            self.t1_hit = True
            self.t1_first_seen_at = timestamp_iso
            self.t1_bid = bid
            self.t1_quote_time = exchange_time or timestamp_iso
            self.t1_quote_id = quote_id
            outcome["t1_crossed_now"] = True
        if self.t2_price is not None and not self.t2_hit and bid >= self.t2_price:
            self.t2_hit = True
            self.t2_first_seen_at = timestamp_iso
            self.t2_bid = bid
            outcome["t2_crossed_now"] = True
        if self.t3_price is not None and not self.t3_hit and bid >= self.t3_price:
            self.t3_hit = True
            self.t3_first_seen_at = timestamp_iso
            self.t3_bid = bid
            outcome["t3_crossed_now"] = True
        if self.sl_price is not None and not self.sl_hit and bid <= self.sl_price:
            self.sl_hit = True
            self.sl_first_seen_at = timestamp_iso
            self.sl_bid = bid
            self.sl_quote_time = exchange_time or timestamp_iso
            self.sl_quote_id = quote_id
            outcome["sl_crossed_now"] = True

        # result transition (never flips)
        if self._result == NONE:
            if outcome["t1_crossed_now"] and outcome["sl_crossed_now"]:
                self._result = AMBIGUOUS
            elif outcome["t1_crossed_now"]:
                self._result = T1_FIRST
            elif outcome["sl_crossed_now"]:
                self._result = SL_FIRST

        outcome["result"] = self._result
        return outcome

    def to_state(self):
        return {
            "t1_price": self.t1_price,
            "t2_price": self.t2_price,
            "t3_price": self.t3_price,
            "sl_price": self.sl_price,
            "t1_hit": self.t1_hit,
            "t2_hit": self.t2_hit,
            "t3_hit": self.t3_hit,
            "sl_hit": self.sl_hit,
            "t1_first_seen_at": self.t1_first_seen_at,
            "sl_first_seen_at": self.sl_first_seen_at,
            "t2_first_seen_at": self.t2_first_seen_at,
            "t3_first_seen_at": self.t3_first_seen_at,
            "t1_bid": self.t1_bid,
            "sl_bid": self.sl_bid,
            "t2_bid": self.t2_bid,
            "t3_bid": self.t3_bid,
            "t1_quote_time": self.t1_quote_time,
            "sl_quote_time": self.sl_quote_time,
            "t1_quote_id": self.t1_quote_id,
            "sl_quote_id": self.sl_quote_id,
            "last_valid_bid": self.last_valid_bid,
            "last_valid_quote_time": self.last_valid_quote_time,
            "first_touch_sequence": self.first_touch_sequence,
            "first_touch_result": self._result,
        }

    @classmethod
    def from_state(cls, state):
        """Exact reconstruction from to_state() output."""
        t = cls(
            t1_price=state.get("t1_price"),
            t2_price=state.get("t2_price"),
            t3_price=state.get("t3_price"),
            sl_price=state.get("sl_price"),
        )
        t.t1_hit = bool(state.get("t1_hit"))
        t.t2_hit = bool(state.get("t2_hit"))
        t.t3_hit = bool(state.get("t3_hit"))
        t.sl_hit = bool(state.get("sl_hit"))
        t.t1_first_seen_at = state.get("t1_first_seen_at")
        t.sl_first_seen_at = state.get("sl_first_seen_at")
        t.t2_first_seen_at = state.get("t2_first_seen_at")
        t.t3_first_seen_at = state.get("t3_first_seen_at")
        t.t1_bid = state.get("t1_bid")
        t.sl_bid = state.get("sl_bid")
        t.t2_bid = state.get("t2_bid")
        t.t3_bid = state.get("t3_bid")
        t.t1_quote_time = state.get("t1_quote_time")
        t.sl_quote_time = state.get("sl_quote_time")
        t.t1_quote_id = state.get("t1_quote_id")
        t.sl_quote_id = state.get("sl_quote_id")
        t.last_valid_bid = state.get("last_valid_bid")
        t.last_valid_quote_time = state.get("last_valid_quote_time")
        t.first_touch_sequence = int(state.get("first_touch_sequence") or 0)
        _r = state.get("first_touch_result")
        t._result = _r if _r in (NONE, T1_FIRST, SL_FIRST, AMBIGUOUS) else NONE
        return t


if __name__ == "__main__":
    print("first_touch_tracker module loaded OK")
    t = EquityFirstTouchTracker(115.0, 130.0, 150.0, 92.0)
    print("init:", t.result())
    print("cross t1:", t.ingest_bid(116.0, "2026-09-16T09:30:00+05:30"))
    print("cross sl later:", t.ingest_bid(91.0, "2026-09-16T09:35:00+05:30"))
    print("final:", t.result())
