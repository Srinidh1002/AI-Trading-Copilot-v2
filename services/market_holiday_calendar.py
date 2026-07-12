"""
Indian market holiday calendar.

Provides trading-holiday checks for the
live market-session safety system.

The calendar is intentionally separate from
the market-session guard so holiday data can
later be loaded from:
- NSE
- Broker APIs
- Configuration files
- Cached holiday data

This module does not place orders.
"""

from datetime import (
    date,
    datetime,
)


class MarketHolidayCalendar:
    """
    Manage Indian market trading holidays.
    """

    def __init__(
        self,
        holidays=None,
    ):
        self.holidays = set()

        if holidays:

            for holiday in holidays:
                self.add_holiday(
                    holiday
                )

    @staticmethod
    def _normalize_date(
        value,
    ):
        """
        Convert supported date values into
        a standard datetime.date object.

        Supported:
        - datetime.date
        - datetime.datetime
        - YYYY-MM-DD string
        """

        if isinstance(
            value,
            datetime,
        ):
            return value.date()

        if isinstance(
            value,
            date,
        ):
            return value

        cleaned = str(
            value
        ).strip()

        if not cleaned:
            raise ValueError(
                "Holiday date cannot be empty."
            )

        try:
            return date.fromisoformat(
                cleaned
            )

        except ValueError as exc:
            raise ValueError(
                "Holiday date must use "
                "YYYY-MM-DD format."
            ) from exc

    def add_holiday(
        self,
        holiday_date,
    ):
        """
        Add a trading holiday.
        """

        normalized = (
            self._normalize_date(
                holiday_date
            )
        )

        self.holidays.add(
            normalized
        )

    def remove_holiday(
        self,
        holiday_date,
    ):
        """
        Remove a trading holiday if present.
        """

        normalized = (
            self._normalize_date(
                holiday_date
            )
        )

        self.holidays.discard(
            normalized
        )

    def is_holiday(
        self,
        value,
    ):
        """
        Return True when the supplied date
        is a configured trading holiday.
        """

        normalized = (
            self._normalize_date(
                value
            )
        )

        return (
            normalized
            in self.holidays
        )

    def get_holidays(
        self,
    ):
        """
        Return configured holidays in
        sorted ISO-date format.
        """

        return [
            holiday.isoformat()
            for holiday
            in sorted(
                self.holidays
            )
        ]