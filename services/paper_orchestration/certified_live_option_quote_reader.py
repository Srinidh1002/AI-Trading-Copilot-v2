from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Protocol
from zoneinfo import ZoneInfo

from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class MarketClient(Protocol):
    def get_ltp(
        self,
        exchange: str,
        tradingsymbol: str,
        symboltoken: str,
    ) -> Mapping[str, object]: ...


class InstrumentMaster(Protocol):
    def get_option_contracts(
        self,
        underlying: str,
        exchange: str = "NFO",
    ) -> list[Mapping[str, object]]: ...


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


_IST = ZoneInfo("Asia/Kolkata")
_ANGEL_TIMESTAMP_FORMAT = "%d-%b-%Y %H:%M:%S"
_MAXIMUM_QUOTE_AGE_SECONDS = 300.0
_MAXIMUM_FUTURE_SKEW_SECONDS = 5.0
_PROVIDER_TIMESTAMP_FIELDS = (
    "exchFeedTime",
    "exchangeTimestamp",
    "timestamp",
)


def _parse_provider_timestamp(
    value: object,
) -> datetime:
    if isinstance(value, datetime):
        parsed = value

    elif (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ):
        numeric = float(value)

        if numeric > 100_000_000_000:
            numeric /= 1000.0

        try:
            parsed = datetime.fromtimestamp(
                numeric,
                tz=timezone.utc,
            )
        except (
            OverflowError,
            OSError,
            ValueError,
        ) as exc:
            raise ValueError(
                "provider timestamp is invalid"
            ) from exc

    elif isinstance(value, str) and value.strip():
        raw = value.strip()

        try:
            parsed = datetime.fromisoformat(
                raw.replace("Z", "+00:00")
            )
        except ValueError:
            try:
                parsed = datetime.strptime(
                    raw,
                    _ANGEL_TIMESTAMP_FORMAT,
                ).replace(tzinfo=_IST)
            except ValueError as exc:
                raise ValueError(
                    "provider timestamp is invalid"
                ) from exc

    else:
        raise ValueError(
            "provider timestamp is missing"
        )

    return _aware(
        parsed,
        "provider timestamp",
    )


def _provider_timestamp_from_data(
    data: Mapping[str, object],
) -> datetime:
    field = next(
        (
            name
            for name in _PROVIDER_TIMESTAMP_FIELDS
            if data.get(name) is not None
        ),
        None,
    )

    if field is None:
        raise ValueError(
            "provider timestamp is missing"
        )

    return _parse_provider_timestamp(
        data[field]
    )


def _positive_float(value: object, name: str) -> float:
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise TypeError(f"{name} must be numeric")

    result = float(value)

    if result <= 0:
        raise ValueError(f"{name} must be greater than zero")

    return result


def derivative_exchange_for(
    underlying_symbol: str,
    persisted_exchange: str | None,
) -> str:
    symbol = _text(
        underlying_symbol,
        "underlying_symbol",
    ).upper()

    exchange = (
        str(persisted_exchange).strip().upper()
        if persisted_exchange is not None
        else ""
    )

    expected = {
        "NIFTY": "NFO",
        "SENSEX": "BFO",
    }

    if symbol not in expected:
        raise ValueError(
            "only NIFTY and SENSEX option positions are supported"
        )

    if exchange in {"NFO", "BFO"}:
        if exchange != expected[symbol]:
            raise ValueError(
                "persisted derivative exchange does not match underlying"
            )
        return exchange

    return expected[symbol]


@dataclass(frozen=True, slots=True)
class CertifiedLiveOptionQuoteV1:
    paper_trade_id: str
    position_id: str
    underlying_symbol: str
    option_symbol: str
    option_exchange: str
    symboltoken: str
    option_last_price: float
    provider_timestamp: datetime
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False
    schema_version: str = "certified_live_option_quote.v1"

    def __post_init__(self) -> None:
        for name in (
            "paper_trade_id",
            "position_id",
            "underlying_symbol",
            "option_symbol",
            "option_exchange",
            "symboltoken",
        ):
            value = _text(getattr(self, name), name)

            if name in {
                "underlying_symbol",
                "option_exchange",
            }:
                value = value.upper()

            object.__setattr__(self, name, value)

        object.__setattr__(
            self,
            "option_last_price",
            _positive_float(
                self.option_last_price,
                "option_last_price",
            ),
        )
        object.__setattr__(
            self,
            "provider_timestamp",
            _aware(
                self.provider_timestamp,
                "provider_timestamp",
            ),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.broker_order_submission:
            raise ValueError(
                "broker order submission must remain disabled"
            )
        if self.schema_version != "certified_live_option_quote.v1":
            raise ValueError("unsupported schema_version")


class CertifiedLiveOptionQuoteReader:
    """Resolve and read one persisted PAPER option position.

    This authority is read-only. It resolves the exact persisted option symbol
    against Angel's instrument master and performs one LTP market-data request.
    """

    def __init__(
        self,
        *,
        market_client: MarketClient,
        instrument_master: InstrumentMaster,
        clock: Clock,
    ) -> None:
        if not callable(
            getattr(
                market_client,
                "get_ltp",
                None,
            )
        ):
            raise TypeError("market_client must expose get_ltp()")

        if not callable(
            getattr(
                instrument_master,
                "get_option_contracts",
                None,
            )
        ):
            raise TypeError(
                "instrument_master must expose get_option_contracts()"
            )

        if not callable(clock):
            raise TypeError("clock must be callable")

        self.market_client = market_client
        self.instrument_master = instrument_master
        self.clock = clock

    @staticmethod
    def _resolve_symboltoken(
        *,
        contracts: object,
        option_symbol: str,
    ) -> str:
        if not isinstance(contracts, list):
            raise TypeError(
                "instrument master contracts must be a list"
            )

        expected_symbol = _text(
            option_symbol,
            "option_symbol",
        ).upper()

        matches: list[str] = []

        for contract in contracts:
            if not isinstance(contract, Mapping):
                raise TypeError(
                    "instrument master contract must be a mapping"
                )

            symbol = str(
                contract.get(
                    "symbol",
                    contract.get(
                        "tradingsymbol",
                        "",
                    ),
                )
            ).strip().upper()

            if symbol != expected_symbol:
                continue

            raw_token = contract.get(
                "token",
                contract.get("symboltoken"),
            )

            if raw_token is None:
                raise ValueError(
                    "matched option contract has no symboltoken"
                )

            token = str(raw_token).strip()

            if not token:
                raise ValueError(
                    "matched option contract has a blank symboltoken"
                )

            matches.append(token)

        if not matches:
            raise ValueError(
                "persisted option symbol was not found "
                "in the instrument master"
            )

        unique = tuple(dict.fromkeys(matches))

        if len(unique) != 1:
            raise ValueError(
                "persisted option symbol resolved to multiple tokens"
            )

        return unique[0]

    def __call__(
        self,
        snapshot: PaperTradePersistenceSnapshotV1,
    ) -> CertifiedLiveOptionQuoteV1:
        if type(snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError(
                "snapshot must be exact "
                "PaperTradePersistenceSnapshotV1"
            )

        position = snapshot.position

        if position is None:
            raise ValueError(
                "live option quote requires a persisted position"
            )

        if snapshot.lifecycle_state.is_terminal:
            raise ValueError(
                "terminal PAPER position must not be quoted"
            )

        if position.lifecycle_state not in {
            "OPEN",
            "PARTIALLY_EXITED",
        }:
            raise ValueError(
                "only active PAPER positions may be quoted"
            )

        option_exchange = derivative_exchange_for(
            position.underlying_symbol,
            position.exchange,
        )

        contracts = self.instrument_master.get_option_contracts(
            underlying=position.underlying_symbol,
            exchange=option_exchange,
        )

        symboltoken = self._resolve_symboltoken(
            contracts=contracts,
            option_symbol=position.option_symbol,
        )

        response = self.market_client.get_ltp(
            exchange=option_exchange,
            tradingsymbol=position.option_symbol,
            symboltoken=symboltoken,
        )

        if not isinstance(response, Mapping):
            raise TypeError(
                "market client get_ltp() must return a mapping"
            )

        if response.get("status") is not True:
            raise ValueError(
                "provider option quote status must be true"
            )

        data = response.get("data")

        if not isinstance(data, Mapping):
            raise ValueError(
                "market client response must contain a data mapping"
            )

        returned_symbol = str(
            data.get("tradingsymbol", "")
        ).strip().upper()
        returned_exchange = str(
            data.get("exchange", "")
        ).strip().upper()
        returned_token = str(
            data.get("symboltoken", "")
        ).strip()

        if returned_symbol != position.option_symbol.upper():
            raise ValueError(
                "provider option symbol does not match persisted position"
            )
        if returned_exchange != option_exchange:
            raise ValueError(
                "provider exchange does not match persisted position"
            )
        if returned_token != symboltoken:
            raise ValueError(
                "provider symboltoken does not match resolved token"
            )

        received_at = _aware(
            self.clock(),
            "clock result",
        )

        provider_timestamp = (
            _provider_timestamp_from_data(data)
        )

        quote_age_seconds = (
            received_at
            - provider_timestamp
        ).total_seconds()

        if (
            quote_age_seconds
            > _MAXIMUM_QUOTE_AGE_SECONDS
        ):
            raise ValueError(
                "provider option quote timestamp is stale"
            )

        if (
            quote_age_seconds
            < -_MAXIMUM_FUTURE_SKEW_SECONDS
        ):
            raise ValueError(
                "provider option quote timestamp exceeds "
                "allowed future skew"
            )

        return CertifiedLiveOptionQuoteV1(
            paper_trade_id=snapshot.paper_trade_id,
            position_id=position.position_id,
            underlying_symbol=position.underlying_symbol,
            option_symbol=position.option_symbol,
            option_exchange=option_exchange,
            symboltoken=symboltoken,
            option_last_price=_positive_float(
                data.get("ltp"),
                "ltp",
            ),
            provider_timestamp=provider_timestamp,
        )