"""Replay clock — Asia/Kolkata tz-aware. Immutable progression."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class ReplayClock:
    def __init__(self, start_ist, step_seconds=60, end_ist=None):
        if start_ist.tzinfo is None:
            start_ist = start_ist.replace(tzinfo=IST)
        else:
            start_ist = start_ist.astimezone(IST)
        if end_ist is not None and end_ist.tzinfo is None:
            end_ist = end_ist.replace(tzinfo=IST)
        elif end_ist is not None:
            end_ist = end_ist.astimezone(IST)
        self._start = start_ist
        self._current = start_ist
        self._step = timedelta(seconds=step_seconds)
        self._end = end_ist
        self._step_count = 0

    @property
    def now(self):
        return self._current

    @property
    def start(self):
        return self._start

    @property
    def step_count(self):
        return self._step_count

    def advance(self):
        nxt = self._current + self._step
        if self._end is not None and nxt > self._end:
            return False
        self._current = nxt
        self._step_count += 1
        return True

    def is_exhausted(self):
        return self._end is not None and self._current >= self._end


if __name__ == "__main__":
    from datetime import datetime as _dt
    rc = ReplayClock(_dt(2026, 9, 11, 17, 0), step_seconds=60,
                     end_ist=_dt(2026, 9, 11, 17, 3))
    for _ in range(10):
        print(f"{rc.now.isoformat()} step={rc.step_count} tz={rc.now.tzinfo}")
        if not rc.advance():
            break
