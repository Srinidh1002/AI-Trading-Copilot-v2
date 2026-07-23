"""
Market Clock

Provides centralized market timing utilities
for the AI Trading Copilot.

Responsibilities
----------------
✓ Market Status
✓ Trading Session Detection
✓ Time Until Open
✓ Time Until Close
✓ Trading Day Check
✓ Session Summary
"""

from __future__ import annotations

from datetime import datetime, timedelta, time


class MarketClock:

    MARKET_OPEN = time(9, 15)

    MARKET_CLOSE = time(15, 30)

    # --------------------------------------------------

    @staticmethod
    def now() -> datetime:

        return datetime.now()

    # --------------------------------------------------

    @classmethod
    def is_trading_day(cls) -> bool:

        return cls.now().weekday() < 5

    # --------------------------------------------------

    @classmethod
    def is_market_open(cls) -> bool:

        if not cls.is_trading_day():

            return False

        current = cls.now().time()

        return cls.MARKET_OPEN <= current <= cls.MARKET_CLOSE

    # --------------------------------------------------

    @classmethod
    def current_session(cls) -> str:

        if not cls.is_trading_day():

            return "WEEKEND"

        current = cls.now().time()

        if current < cls.MARKET_OPEN:

            return "PRE_MARKET"

        if current <= cls.MARKET_CLOSE:

            return "LIVE_MARKET"

        return "POST_MARKET"

    # --------------------------------------------------

    @classmethod
    def next_market_open(cls) -> datetime:

        now = cls.now()

        next_open = datetime.combine(

            now.date(),

            cls.MARKET_OPEN,

        )

        if now < next_open and cls.is_trading_day():

            return next_open

        next_day = now + timedelta(days=1)

        while next_day.weekday() >= 5:

            next_day += timedelta(days=1)

        return datetime.combine(

            next_day.date(),

            cls.MARKET_OPEN,

        )

    # --------------------------------------------------

    @classmethod
    def next_market_close(cls) -> datetime:

        now = cls.now()

        close = datetime.combine(

            now.date(),

            cls.MARKET_CLOSE,

        )

        if cls.is_market_open():

            return close

        return datetime.combine(

            cls.next_market_open().date(),

            cls.MARKET_CLOSE,

        )

    # --------------------------------------------------

    @classmethod
    def time_until_open(cls) -> timedelta:

        return cls.next_market_open() - cls.now()

    # --------------------------------------------------

    @classmethod
    def time_until_close(cls) -> timedelta:

        return cls.next_market_close() - cls.now()

    # --------------------------------------------------

    @classmethod
    def seconds_until_open(cls) -> int:

        return max(

            0,

            int(

                cls.time_until_open().total_seconds()

            ),

        )

    # --------------------------------------------------

    @classmethod
    def seconds_until_close(cls) -> int:

        return max(

            0,

            int(

                cls.time_until_close().total_seconds()

            ),

        )

    # --------------------------------------------------

    @classmethod
    def summary(cls):

        return {

            "market_open": cls.is_market_open(),

            "trading_day": cls.is_trading_day(),

            "session": cls.current_session(),

            "current_time": cls.now().strftime(

                "%Y-%m-%d %H:%M:%S"

            ),

            "seconds_until_open": cls.seconds_until_open(),

            "seconds_until_close": cls.seconds_until_close(),

        }