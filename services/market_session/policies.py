from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import time


@dataclass(
    frozen=True,
    slots=True,
)
class MarketSessionPolicy:
    timezone: str = "Asia/Kolkata"
    pre_open_start: time = time(9, 0)
    pre_open_order_entry_end: time = time(9, 8)
    pre_open_matching_end: time = time(9, 12)
    regular_open: time = time(9, 15)
    new_entry_cutoff: time = time(15, 20)
    regular_close: time = time(15, 40)
    max_snapshot_age_seconds: float = 300.0
    max_future_skew_seconds: float = 5.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.timezone, str)
            or not self.timezone.strip()
        ):
            raise ValueError(
                "timezone must be a non-empty string."
            )

        boundaries = (
            self.pre_open_start,
            self.pre_open_order_entry_end,
            self.pre_open_matching_end,
            self.regular_open,
            self.new_entry_cutoff,
            self.regular_close,
        )

        if not all(
            isinstance(value, time)
            for value in boundaries
        ):
            raise TypeError(
                "Session boundaries must be datetime.time values."
            )

        if not (
            self.pre_open_start
            <= self.pre_open_order_entry_end
            <= self.pre_open_matching_end
            <= self.regular_open
            < self.new_entry_cutoff
            < self.regular_close
        ):
            raise ValueError(
                "Market session boundaries are not ordered."
            )

        for name in (
            "max_snapshot_age_seconds",
            "max_future_skew_seconds",
        ):
            value = getattr(self, name)

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) < 0
            ):
                raise ValueError(
                    f"{name} must be finite and non-negative."
                )


NSE_NIFTY_POLICY = MarketSessionPolicy()
BSE_SENSEX_POLICY = MarketSessionPolicy()
