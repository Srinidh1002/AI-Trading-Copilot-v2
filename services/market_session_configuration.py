"""
Market-session configuration boundary.

Resolves exchange-specific session safety dependencies
from the canonical live market configuration.
"""

from dataclasses import dataclass

from services.bse_holiday_calendar import (
    get_bse_holiday_calendar,
)
from services.live_market_configuration import (
    resolve_live_market_configuration,
)
from services.nse_holiday_calendar import (
    get_nse_holiday_calendar,
)


@dataclass(
    frozen=True
)
class MarketSessionConfiguration:
    underlying: str
    exchange: str
    option_exchange: str
    holiday_calendar: object


def resolve_market_session_configuration(
    underlying=None,
):
    market_configuration = (
        resolve_live_market_configuration(
            underlying
        )
    )

    exchange = str(
        market_configuration.exchange
    ).strip().upper()

    if exchange == "NSE":
        holiday_calendar = (
            get_nse_holiday_calendar()
        )

    elif exchange == "BSE":
        holiday_calendar = (
            get_bse_holiday_calendar()
        )

    else:
        raise ValueError(
            f"Unsupported market-session "
            f"exchange: {exchange}."
        )

    return MarketSessionConfiguration(
        underlying=(
            market_configuration.underlying
        ),
        exchange=exchange,
        option_exchange=(
            market_configuration.option_exchange
        ),
        holiday_calendar=holiday_calendar,
    )
