"""Previous Day Engine - Computes PDH/PDL/PDC and classifies prior session.
Used as baseline context for today's trading.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class PreviousDayEngine:
    def __init__(
        self, obj, market="NIFTY", index_exchange="NSE", index_token="99926000", rate_limiter=None
    ):
        self.obj = obj
        self.market = market.upper()
        self.exchange = index_exchange
        self.token = index_token
        self.rate_limiter = rate_limiter
        self._cache = None
        self._cache_date = None

    def fetch(self, force=False):
        """Fetch previous completed session's OHLC and classify."""
        today = datetime.now().date()
        if not force and self._cache is not None and self._cache_date == today:
            return self._cache

        try:
            # Look back 7 calendar days to get last 3 completed sessions
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d 09:15")
            to_date = datetime.now().strftime("%Y-%m-%d 15:30")

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

            if not candles or not candles.get("data") or len(candles["data"]) < 2:
                return self._unavailable("INSUFFICIENT_HISTORY")

            data = candles["data"]
            # Last entry is today (incomplete); previous is prior session
            prev = None
            prev_date = None

            for row in reversed(data):
                try:
                    raw_timestamp = row[0]

                    if isinstance(raw_timestamp, (int, float)):
                        row_date = datetime.fromtimestamp(
                            float(raw_timestamp),
                            tz=ZoneInfo("Asia/Kolkata"),
                        ).date()
                    else:
                        raw_text = str(raw_timestamp).strip()

                        try:
                            epoch_value = float(raw_text)
                        except ValueError:
                            epoch_value = None

                        if epoch_value is not None:
                            row_date = datetime.fromtimestamp(
                                epoch_value,
                                tz=ZoneInfo("Asia/Kolkata"),
                            ).date()
                        else:
                            row_date = datetime.fromisoformat(
                                raw_text.replace("Z", "+00:00")
                            ).date()

                    if row_date < today:
                        prev = row
                        prev_date = row_date
                        break

                except (TypeError, ValueError, OSError, OverflowError):
                    continue

            if prev is None:
                return self._unavailable("NO_PRIOR_SESSION")

            o = float(prev[1])
            h = float(prev[2])
            low = float(prev[3])
            c = float(prev[4])
            rng = h - low
            body = abs(c - o)
            direction = "UP" if c > o else ("DOWN" if c < o else "FLAT")

            # Classify prior day
            if rng > 0:
                close_loc = (c - low) / rng  # 0 = low, 1 = high
            else:
                close_loc = 0.5

            # Day type heuristic
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

            # ATR(14) from daily data
            atr = self._compute_atr(data, period=14)

            result = {
                "status": "OK",
                "date": prev_date.isoformat() if prev_date else None,
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
                "today_open_estimate": None,  # Filled by bot's get_day_open
            }

            self._cache = result
            self._cache_date = today
            return result

        except Exception as e:
            return self._unavailable(f"ERROR:{str(e)[:40]}")

    def _compute_atr(self, data, period=14):
        """Simple ATR from daily OHLC list."""
        try:
            trs = []
            for i in range(1, min(len(data), period + 1)):
                h = float(data[-i][2])
                low = float(data[-i][3])
                pc = float(data[-i - 1][4])
                tr = max(h - low, abs(h - pc), abs(low - pc))
                trs.append(tr)
            return sum(trs) / len(trs) if trs else None
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
