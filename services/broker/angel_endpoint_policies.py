"""Documented Angel SmartAPI endpoint limits and conservative local policy."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AngelEndpointPolicyV1:
    endpoint: str
    requests_per_second: int
    requests_per_minute: int | None
    requests_per_hour: int | None


DOCUMENTED_ENDPOINT_POLICIES = {
    "historical-data": AngelEndpointPolicyV1("historical-data", 3, 150, 5000),
    "market-quote": AngelEndpointPolicyV1("market-quote", 10, 500, 5000),
    "ltp": AngelEndpointPolicyV1("ltp", 10, 500, 5000),
    "option-greeks": AngelEndpointPolicyV1("option-greeks", 1, None, None),
}

# Client-code-wide rate limiting means the process deliberately reserves headroom.
CONSERVATIVE_HISTORICAL_POLICY = AngelEndpointPolicyV1(
    "historical-data", 1, 120, 4000
)

# Angel's Market Data page documents one quote request per second, while its
# rate-limit page advertises a higher burst limit.  Certified reads use the
# stricter published value until the provider reconciles that discrepancy.
CONSERVATIVE_MARKET_QUOTE_POLICY = AngelEndpointPolicyV1(
    "market-quote", 1, None, None
)

HISTORICAL_MAX_LOOKBACK_DAYS = {
    "ONE_MINUTE": 30,
    "THREE_MINUTE": 60,
    "FIVE_MINUTE": 100,
    "TEN_MINUTE": 100,
    "FIFTEEN_MINUTE": 200,
    "THIRTY_MINUTE": 200,
    "ONE_HOUR": 400,
    "ONE_DAY": 2000,
}


def validate_historical_timeframe_config(config: dict[str, dict[str, object]]) -> None:
    for timeframe, value in config.items():
        interval = value.get("interval")
        days = value.get("lookback_days")
        if interval not in HISTORICAL_MAX_LOOKBACK_DAYS:
            raise ValueError(f"unsupported Angel historical interval: {interval}")
        if type(days) not in (int, float) or isinstance(days, bool) or days <= 0:
            raise ValueError(f"invalid historical lookback for {timeframe}")
        if days > HISTORICAL_MAX_LOOKBACK_DAYS[interval]:
            raise ValueError(f"Angel historical maximum exceeded for {timeframe}")
