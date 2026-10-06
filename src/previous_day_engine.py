"""Previous Day Engine - Computes PDH/PDL/PDC and classifies prior session.

Used as baseline context for today's trading.  R19-C2 accepts the timestamp
shape emitted by both the legacy compatibility path and native FYERS history:
ISO timestamps or epoch seconds.  Only completed sessions strictly before the
current IST trading date are eligible.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _now_ist() -> datetime:
    return datetime.now(IST)


def _parse_candle_datetime(value: object) -> datetime | None:
    """Normalize a candle timestamp to an aware IST datetime.

    FYERS history with date_format=0 emits epoch seconds.  Older test fixtures
    and some compatibility callers may still supply ISO text.  Unsupported or
    non-finite values fail closed and are ignored by the session selector.
    """

    if isinstance(value, bool):
        return None

    epoch_value: float | None = None

    if isinstance(value, (int, float)):
        epoch_value = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        try:
            epoch_value = float(text)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(
                    text.replace("Z", "+00:00")
                )
            except ValueError:
                return None

            if parsed.tzinfo is None or parsed.utcoffset() is None:
                parsed = parsed.replace(tzinfo=IST)
            else:
                parsed = parsed.astimezone(IST)

            return parsed
    else:
        return None

    if epoch_value is None or not math.isfinite(epoch_value):
        return None

    # Defensive support for millisecond epochs without weakening the FYERS
    # seconds contract.
    if abs(epoch_value) >= 10_000_000_000:
        epoch_value /= 1000.0

    try:
        return datetime.fromtimestamp(epoch_value, tz=IST)
    except (OverflowError, OSError, ValueError):
        return None


class PreviousDayEngine:
    def __init__(
        self,
        obj,
        market="NIFTY",
        index_exchange="NSE",
        index_token="99926000",
        rate_limiter=None,
    ):
        self.obj = obj
        self.market = market.upper()
        self.exchange = index_exchange
        self.token = index_token
        self.rate_limiter = rate_limiter
        self._cache = None
        self._cache_date = None

    def fetch(self, force=False):
        """Fetch the latest completed session's OHLC and classify it."""

        now = _now_ist()
        today = now.date()

        if (
            not force
            and self._cache is not None
            and self._cache_date == today
        ):
            return self._cache

        try:
            # Seven calendar days normally spans at least one completed Indian
            # trading session while keeping the provider request small.
            from_date = (
                now - timedelta(days=7)
            ).strftime("%Y-%m-%d 09:15")
            to_date = now.strftime("%Y-%m-%d 15:30")

            if self.rate_limiter:
                self.rate_limiter.wait_if_needed("get_candle_data")

            candles = self.obj.getCandleData(
                {
                    "exchange": self.exchange,
                    "symboltoken": self.token,
                    "interval": "ONE_DAY",
                    "fromdate": from_date,
                    "todate": to_date,
                }
            )

            data = (
                candles.get("data")
                if isinstance(candles, dict)
                else None
            )

            if not isinstance(data, list) or not data:
                return self._unavailable("INSUFFICIENT_HISTORY")

            parsed_rows = []

            for row in data:
                if (
                    not isinstance(row, (list, tuple))
                    or len(row) < 5
                ):
                    continue

                row_dt = _parse_candle_datetime(row[0])

                if row_dt is None:
                    continue

                parsed_rows.append((row_dt, row))

            if not parsed_rows:
                return self._unavailable(
                    "UNPARSEABLE_HISTORY_TIMESTAMP"
                )

            completed_rows = [
                (row_dt, row)
                for row_dt, row in parsed_rows
                if row_dt.date() < today
            ]

            if not completed_rows:
                return self._unavailable("NO_PRIOR_SESSION")

            # Do not rely on provider row ordering.  Select the newest strictly
            # prior completed session by normalized timestamp.
            completed_rows.sort(key=lambda item: item[0])
            prev_dt, prev = completed_rows[-1]

            o = float(prev[1])
            h = float(prev[2])
            low = float(prev[3])
            c = float(prev[4])

            rng = h - low
            body = abs(c - o)
            direction = (
                "UP"
                if c > o
                else ("DOWN" if c < o else "FLAT")
            )

            if rng > 0:
                close_loc = (c - low) / rng
            else:
                close_loc = 0.5

            range_pct = (rng / o) * 100 if o > 0 else 0
            body_pct = (body / o) * 100 if o > 0 else 0

            if body_pct > 0.6 and close_loc > 0.7:
                day_type = "TREND_UP"
            elif body_pct > 0.6 and close_loc < 0.3:
                day_type = "TREND_DOWN"
            elif range_pct > 1.5:
                day_type = "HIGH_VOLATILITY"
            elif range_pct < 0.5:
                day_type = "LOW_VOLATILITY"
            else:
                day_type = "RANGE_DAY"

            # ATR must use only completed sessions.  A current-day partial
            # daily candle must never contaminate prior-session context.
            completed_data = [
                row
                for _, row in completed_rows
            ]
            atr = self._compute_atr(
                completed_data,
                period=14,
            )

            result = {
                "status": "OK",
                "date": prev_dt.date().isoformat(),
                "open": o,
                "high": h,
                "low": low,
                "close": c,
                "range": rng,
                "range_pct": range_pct,
                "body_pct": body_pct,
                "direction": direction,
                "close_location": close_loc,
                "day_type": day_type,
                "atr14": atr,
                "today_open_estimate": None,
            }

            self._cache = result
            self._cache_date = today
            return result

        except Exception as exc:
            return self._unavailable(
                f"ERROR:{str(exc)[:40]}"
            )

    def _compute_atr(self, data, period=14):
        """Simple ATR from chronologically sorted completed daily OHLC rows."""

        try:
            trs = []

            for i in range(
                1,
                min(len(data), period + 1),
            ):
                h = float(data[-i][2])
                low = float(data[-i][3])
                pc = float(data[-i - 1][4])
                tr = max(
                    h - low,
                    abs(h - pc),
                    abs(low - pc),
                )
                trs.append(tr)

            return (
                sum(trs) / len(trs)
                if trs
                else None
            )
        except Exception:
            return None

    def _unavailable(self, reason):
        return {
            "status": "EVIDENCE_UNAVAILABLE",
            "reason": reason,
            "date": None,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "range": None,
            "range_pct": None,
            "body_pct": None,
            "direction": None,
            "close_location": None,
            "day_type": None,
            "atr14": None,
        }


if __name__ == "__main__":
    print("PreviousDayEngine module loaded OK")
    print("Methods: fetch(), _compute_atr()")
