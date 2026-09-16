"""Canonical provider-resolved instrument identity for the five-market universe."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import math

from services.core.five_market_universe_v2 import (
    get_target_market,
)


_PROVIDER_IDS = {
    "FYERS",
    "ANGEL_SMARTAPI",
}

_INSTRUMENT_TYPES = {
    "UNDERLYING",
    "FUTURE",
    "OPTION",
}

_OPTION_TYPES = {
    "CE",
    "PE",
}

_METADATA_STATUSES = {
    "NOT_APPLICABLE",
    "VERIFIED",
    "PROVISIONAL",
    "UNAVAILABLE",
}


def _norm(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = " ".join(
        value.upper().split()
    )

    return value or None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()

    return value or None


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _positive_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


@dataclass(frozen=True, slots=True)
class ResolvedInstrumentV2:
    """One provider-specific identity bound to one canonical market instrument."""

    resolution_id: str

    provider: str

    market_symbol: str
    market_type: str

    underlying_exchange: str
    derivative_exchange: str

    instrument_type: str

    canonical_instrument_id: str

    provider_symbol: str
    provider_exchange: str
    provider_token: str | None

    expiry: date | None = None
    strike: float | None = None
    option_type: str | None = None

    lot_size: int | None = None
    tick_size: float | None = None

    contract_metadata_status: str = "UNAVAILABLE"
    metadata_source: str | None = None

    resolved_at: datetime | None = None

    data_only: bool = True
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False

    warnings: tuple[str, ...] = ()

    schema_version: str = "resolved_instrument.v2"

    def __post_init__(self) -> None:
        resolution_id = _text(
            self.resolution_id
        )

        provider = _norm(
            self.provider
        )

        instrument_type = _norm(
            self.instrument_type
        )

        metadata_status = _norm(
            self.contract_metadata_status
        )

        if resolution_id is None:
            raise ValueError(
                "Resolution id is required."
            )

        if provider not in _PROVIDER_IDS:
            raise ValueError(
                "Unsupported provider."
            )

        if instrument_type not in _INSTRUMENT_TYPES:
            raise ValueError(
                "Unsupported instrument type."
            )

        market = get_target_market(
            self.market_symbol
        )

        if (
            _norm(self.market_type)
            != market.market_type
        ):
            raise ValueError(
                "Market type mismatch."
            )

        if (
            _norm(self.underlying_exchange)
            != market.underlying_exchange
        ):
            raise ValueError(
                "Underlying exchange mismatch."
            )

        if (
            _norm(self.derivative_exchange)
            != market.derivative_exchange
        ):
            raise ValueError(
                "Derivative exchange mismatch."
            )

        expected_exchange = (
            market.underlying_exchange
            if instrument_type == "UNDERLYING"
            else market.derivative_exchange
        )

        provider_exchange = _text(
            self.provider_exchange
        )

        if provider_exchange is None:
            raise ValueError(
                "Provider exchange is required."
            )

        if _norm(provider_exchange) is None:
            raise ValueError(
                "Invalid provider exchange."
            )

        canonical_id = _text(
            self.canonical_instrument_id
        )

        provider_symbol = _text(
            self.provider_symbol
        )

        provider_token = (
            _text(
                self.provider_token
            )
            if self.provider_token is not None
            else None
        )

        if canonical_id is None:
            raise ValueError(
                "Canonical instrument id is required."
            )

        if provider_symbol is None:
            raise ValueError(
                "Provider symbol is required."
            )

        if instrument_type == "UNDERLYING":
            if (
                self.expiry is not None
                or self.strike is not None
                or self.option_type is not None
            ):
                raise ValueError(
                    "Underlying cannot carry derivative fields."
                )

            if metadata_status != "NOT_APPLICABLE":
                raise ValueError(
                    "Underlying metadata status must be NOT_APPLICABLE."
                )

            if (
                self.lot_size is not None
                or self.tick_size is not None
            ):
                raise ValueError(
                    "Underlying must not promote derivative contract metadata."
                )

        elif instrument_type == "FUTURE":
            if not isinstance(
                self.expiry,
                date,
            ):
                raise ValueError(
                    "Future expiry is required."
                )

            if (
                self.strike is not None
                or self.option_type is not None
            ):
                raise ValueError(
                    "Future cannot carry option fields."
                )

        elif instrument_type == "OPTION":
            if not isinstance(
                self.expiry,
                date,
            ):
                raise ValueError(
                    "Option expiry is required."
                )

            if not _positive_number(
                self.strike
            ):
                raise ValueError(
                    "Option strike is required."
                )

            option_type = _norm(
                self.option_type
            )

            if option_type not in _OPTION_TYPES:
                raise ValueError(
                    "Invalid option type."
                )

            object.__setattr__(
                self,
                "option_type",
                option_type,
            )

        if instrument_type != "UNDERLYING":
            if metadata_status not in {
                "VERIFIED",
                "PROVISIONAL",
                "UNAVAILABLE",
            }:
                raise ValueError(
                    "Invalid derivative metadata status."
                )

            if self.lot_size is not None:
                if (
                    not isinstance(
                        self.lot_size,
                        int,
                    )
                    or isinstance(
                        self.lot_size,
                        bool,
                    )
                    or self.lot_size < 1
                ):
                    raise ValueError(
                        "Invalid lot size."
                    )

            if (
                self.tick_size is not None
                and not _positive_number(
                    self.tick_size
                )
            ):
                raise ValueError(
                    "Invalid tick size."
                )

            if metadata_status == "VERIFIED":
                if (
                    self.lot_size is None
                    or self.tick_size is None
                ):
                    raise ValueError(
                        "Verified metadata requires lot and tick size."
                    )

            if metadata_status == "UNAVAILABLE":
                if (
                    self.lot_size is not None
                    or self.tick_size is not None
                ):
                    raise ValueError(
                        "Unavailable metadata cannot carry lot/tick values."
                    )

        metadata_source = (
            _text(
                self.metadata_source
            )
            if self.metadata_source is not None
            else None
        )

        if metadata_status in {
            "VERIFIED",
            "PROVISIONAL",
        } and metadata_source is None:
            raise ValueError(
                "Contract metadata source is required."
            )

        if metadata_status in {
            "NOT_APPLICABLE",
            "UNAVAILABLE",
        } and metadata_source is not None:
            raise ValueError(
                "Metadata source is inconsistent with status."
            )

        if not _aware(
            self.resolved_at
        ):
            raise ValueError(
                "Resolved timestamp must be timezone-aware."
            )

        if self.data_only is not True:
            raise ValueError(
                "Resolved instrument must remain data-only."
            )

        if self.execution_mode != "PAPER":
            raise ValueError(
                "Resolved instrument is PAPER only."
            )

        if self.live_execution_eligible is not False:
            raise ValueError(
                "Live execution is not eligible."
            )

        if not isinstance(
            self.warnings,
            tuple,
        ):
            raise ValueError(
                "Warnings must be a tuple."
            )

        if (
            self.schema_version
            != "resolved_instrument.v2"
        ):
            raise ValueError(
                "Invalid resolved-instrument schema."
            )

        object.__setattr__(
            self,
            "resolution_id",
            resolution_id,
        )

        object.__setattr__(
            self,
            "provider",
            provider,
        )

        object.__setattr__(
            self,
            "market_symbol",
            market.symbol,
        )

        object.__setattr__(
            self,
            "market_type",
            market.market_type,
        )

        object.__setattr__(
            self,
            "underlying_exchange",
            market.underlying_exchange,
        )

        object.__setattr__(
            self,
            "derivative_exchange",
            market.derivative_exchange,
        )

        object.__setattr__(
            self,
            "instrument_type",
            instrument_type,
        )

        object.__setattr__(
            self,
            "canonical_instrument_id",
            canonical_id,
        )

        object.__setattr__(
            self,
            "provider_symbol",
            provider_symbol,
        )

        object.__setattr__(
            self,
            "provider_exchange",
            provider_exchange,
        )

        object.__setattr__(
            self,
            "provider_token",
            provider_token,
        )

        object.__setattr__(
            self,
            "contract_metadata_status",
            metadata_status,
        )

        object.__setattr__(
            self,
            "metadata_source",
            metadata_source,
        )

        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )

        # expected_exchange is deliberately not forced onto provider_exchange.
        # Provider naming is adapter-owned and may differ from canonical exchange.
        if not expected_exchange:
            raise ValueError(
                "Canonical exchange resolution failed."
            )

    def to_provider_instrument(
        self,
    ) -> dict[str, object]:
        """Mapping boundary compatible with InstrumentResolverV2."""

        return {
            "resolution_id": self.resolution_id,
            "provider": self.provider,
            "market_symbol": self.market_symbol,
            "market_type": self.market_type,
            "underlying_exchange": (
                self.underlying_exchange
            ),
            "derivative_exchange": (
                self.derivative_exchange
            ),
            "instrument_type": self.instrument_type,
            "canonical_instrument_id": (
                self.canonical_instrument_id
            ),
            "provider_symbol": self.provider_symbol,
            "provider_exchange": self.provider_exchange,
            "provider_token": self.provider_token,
            "expiry": (
                self.expiry.isoformat()
                if self.expiry is not None
                else None
            ),
            "strike": self.strike,
            "option_type": self.option_type,
            "lot_size": self.lot_size,
            "tick_size": self.tick_size,
            "contract_metadata_status": (
                self.contract_metadata_status
            ),
            "metadata_source": self.metadata_source,
            "resolved_at": self.resolved_at.isoformat(),
            "data_only": True,
            "execution_mode": "PAPER",
            "live_execution_eligible": False,
            "warnings": list(self.warnings),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_provider_instrument(),
            sort_keys=True,
            separators=(",", ":"),
        )
