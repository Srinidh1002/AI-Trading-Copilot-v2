from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Mapping


SESSION_STATES = frozenset(
    {
        "PRE_OPEN",
        "OPEN",
        "ENTRY_CUTOFF",
        "POSITION_MANAGEMENT",
        "CLOSED",
        "HOLIDAY",
        "UNKNOWN",
    }
)
DATA_QUALITY_STATUSES = frozenset({"FRESH", "STALE", "PARTIAL", "INVALID"})


def _nonblank_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be an exact str")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def _aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _exact_date(value: object, field_name: str) -> date:
    if type(value) is not date:
        raise TypeError(f"{field_name} must be an exact date")
    return value


def _finite_number(
    value: object,
    field_name: str,
    *,
    required: bool,
    minimum: float,
    strictly_greater: bool = False,
) -> float | None:
    if value is None:
        if required:
            raise ValueError(f"{field_name} is required")
        return None
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    if strictly_greater:
        if numeric <= minimum:
            raise ValueError(f"{field_name} must be greater than {minimum}")
    elif numeric < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
    return numeric


def _price(
    value: object,
    field_name: str,
    *,
    required: bool = False,
) -> float | None:
    return _finite_number(
        value,
        field_name,
        required=required,
        minimum=0.0,
        strictly_greater=True,
    )


def _freeze_json_value(value: Any, *, field_name: str = "metadata") -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must contain finite floats")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, nested in value.items():
            normalized_key = _nonblank_text(key, f"{field_name} key")
            frozen[normalized_key] = _freeze_json_value(
                nested,
                field_name=f"{field_name}.{normalized_key}",
            )
        return MappingProxyType(dict(sorted(frozen.items())))
    if type(value) in (tuple, list):
        return tuple(
            _freeze_json_value(item, field_name=field_name) for item in value
        )
    raise ValueError(f"{field_name} must be JSON-safe")


def _plain_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain_json_value(item) for item in value]
    return value


def _freeze_warnings(value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError("warnings must be an exact tuple")
    return tuple(
        dict.fromkeys(_nonblank_text(item, "warning") for item in value)
    )


def _freeze_source_timestamps(
    value: object,
) -> Mapping[str, datetime]:
    if not isinstance(value, Mapping):
        raise TypeError("source_timestamps must be a mapping")
    normalized: dict[str, datetime] = {}
    for key, timestamp in value.items():
        normalized_key = _nonblank_text(key, "source_timestamps key")
        normalized[normalized_key] = _aware_datetime(
            timestamp,
            f"source_timestamps[{normalized_key}]",
        )
    return MappingProxyType(dict(sorted(normalized.items())))


def _validate_ohlc_group(
    *,
    prefix: str,
    open_price: float | None,
    high_price: float | None,
    low_price: float | None,
    close_price: float | None,
    last_price: float,
) -> None:
    group = (open_price, high_price, low_price, close_price)
    populated = sum(value is not None for value in group)
    if populated not in (0, 4):
        raise ValueError(f"{prefix} OHLC must be all present or all absent")
    if populated == 0:
        return
    assert open_price is not None
    assert high_price is not None
    assert low_price is not None
    assert close_price is not None
    if high_price < low_price:
        raise ValueError(f"{prefix}_high must be at least {prefix}_low")
    for name, value in (
        ("open", open_price),
        ("close", close_price),
        ("last", last_price),
    ):
        if not low_price <= value <= high_price:
            raise ValueError(
                f"{prefix}_{name} must be within {prefix}_low/{prefix}_high"
            )


@dataclass(frozen=True, slots=True)
class PaperMarketObservationV1:
    observation_id: str
    trade_plan_id: str
    integrated_trade_plan_result_id: str
    selected_option_contract_id: str
    observed_at: datetime
    received_at: datetime
    market_session_date: date
    underlying_symbol: str
    underlying_last_price: float
    option_symbol: str
    option_last_price: float
    market: str
    exchange: str
    session_state: str
    is_market_open: bool
    is_expiry_session: bool
    data_quality_status: str
    source: str

    underlying_open: float | None = None
    underlying_high: float | None = None
    underlying_low: float | None = None
    underlying_close: float | None = None
    option_open: float | None = None
    option_high: float | None = None
    option_low: float | None = None
    option_close: float | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    warnings: tuple[str, ...] = ()
    source_timestamps: Mapping[str, datetime] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "observation_id",
            "trade_plan_id",
            "integrated_trade_plan_result_id",
            "selected_option_contract_id",
            "underlying_symbol",
            "option_symbol",
            "market",
            "exchange",
            "source",
        ):
            object.__setattr__(
                self,
                field_name,
                _nonblank_text(getattr(self, field_name), field_name),
            )

        object.__setattr__(
            self,
            "observed_at",
            _aware_datetime(self.observed_at, "observed_at"),
        )
        object.__setattr__(
            self,
            "received_at",
            _aware_datetime(self.received_at, "received_at"),
        )
        object.__setattr__(
            self,
            "market_session_date",
            _exact_date(self.market_session_date, "market_session_date"),
        )
        if self.received_at < self.observed_at:
            raise ValueError("received_at must not precede observed_at")

        for field_name in (
            "underlying_last_price",
            "option_last_price",
        ):
            object.__setattr__(
                self,
                field_name,
                _price(getattr(self, field_name), field_name, required=True),
            )

        for field_name in (
            "underlying_open",
            "underlying_high",
            "underlying_low",
            "underlying_close",
            "option_open",
            "option_high",
            "option_low",
            "option_close",
            "bid_price",
            "ask_price",
        ):
            object.__setattr__(
                self,
                field_name,
                _price(getattr(self, field_name), field_name),
            )

        _validate_ohlc_group(
            prefix="underlying",
            open_price=self.underlying_open,
            high_price=self.underlying_high,
            low_price=self.underlying_low,
            close_price=self.underlying_close,
            last_price=self.underlying_last_price,
        )
        _validate_ohlc_group(
            prefix="option",
            open_price=self.option_open,
            high_price=self.option_high,
            low_price=self.option_low,
            close_price=self.option_close,
            last_price=self.option_last_price,
        )

        if (self.bid_price is None) != (self.ask_price is None):
            raise ValueError("bid_price and ask_price must be supplied together")
        if (
            self.bid_price is not None
            and self.ask_price is not None
            and self.ask_price < self.bid_price
        ):
            raise ValueError("ask_price must be at least bid_price")

        if self.session_state not in SESSION_STATES:
            raise ValueError("unsupported session_state")
        if self.data_quality_status not in DATA_QUALITY_STATUSES:
            raise ValueError("unsupported data_quality_status")
        if type(self.is_market_open) is not bool:
            raise TypeError("is_market_open must be an exact bool")
        if type(self.is_expiry_session) is not bool:
            raise TypeError("is_expiry_session must be an exact bool")

        object.__setattr__(self, "warnings", _freeze_warnings(self.warnings))
        object.__setattr__(
            self,
            "source_timestamps",
            _freeze_source_timestamps(self.source_timestamps),
        )
        object.__setattr__(
            self,
            "metadata",
            _freeze_json_value(self.metadata),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible is not False:
            raise ValueError("live_execution_eligible must be False")
        if self.schema_version != "1.0":
            raise ValueError("schema_version must be 1.0")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if isinstance(value, (datetime, date)):
                result[field_name] = value.isoformat()
            elif field_name == "source_timestamps":
                result[field_name] = {
                    key: timestamp.isoformat()
                    for key, timestamp in self.source_timestamps.items()
                }
            elif field_name == "warnings":
                result[field_name] = list(self.warnings)
            elif field_name == "metadata":
                result[field_name] = _plain_json_value(self.metadata)
            else:
                result[field_name] = value
        return result

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def semantic_dict(self) -> dict[str, Any]:
        result = self.to_dict()
        for field_name in (
            "observation_id",
            "observed_at",
            "received_at",
            "source_timestamps",
        ):
            result.pop(field_name)
        return result
