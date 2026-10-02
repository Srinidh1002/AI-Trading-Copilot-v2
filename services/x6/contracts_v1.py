"""Immutable X6 model assumptions and observations, linked to frozen X5 captures.

No model estimation, provider access, contract selection, orders or PAPER counters.
Prices are in underlying native units per one unit, never lot-level P&L.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone

from services.x5.contracts_v1 import MARKET_EXCHANGES, canonical_sha256

IST = timezone(timedelta(hours=5, minutes=30))
MODEL_BY_MARKET = {
    "NIFTY": "BLACK_SCHOLES_SPOT",
    "SENSEX": "BLACK_SCHOLES_SPOT",
    "CRUDEOILM": "BLACK_76_FUTURES",
    "GOLDM": "BLACK_76_FUTURES",
    "NATGASMINI": "BLACK_76_FUTURES",
}
PRICE_UNITS = {
    "NIFTY": "INDEX_POINTS",
    "SENSEX": "INDEX_POINTS",
    "CRUDEOILM": "INR_PER_BARREL",
    "GOLDM": "INR_PER_10G",
    "NATGASMINI": "INR_PER_MMBTU",
}
_YEAR_SECONDS = 365 * 24 * 60 * 60


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _number(value: object, *, positive: bool = False, signed: bool = False) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and (not positive or value > 0)
        and (signed or value >= 0)
    )


def _sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _disabled_authority(value: object, schema: str) -> None:
    if (
        getattr(value, "schema_version") != schema
        or getattr(value, "data_only") is not True
        or getattr(value, "independent_vote") is not False
        or any(
            getattr(value, name) is not False
            for name in (
                "execution_authority",
                "risk_authority",
                "position_authority",
                "certification_authority",
                "live_execution_eligible",
            )
        )
    ):
        raise ValueError("X6 schema and zero-authority fields are fixed")


@dataclass(frozen=True, slots=True)
class X6PricingContextV1:
    """Explicit inputs; None means unknown, never silently assume r, q or close."""

    market: str
    model: str
    option_expiry: date
    as_of: datetime
    option_expiry_at: datetime | None
    expiry_source_id: str
    reference_price: float | None
    reference_unit: str
    reference_source_id: str
    reference_verified: bool
    annual_risk_free_rate: float | None
    rate_source_id: str | None
    rate_verified: bool
    annual_dividend_yield: float | None = None
    dividend_source_id: str | None = None
    dividend_verified: bool = False
    futures_contract_id: str | None = None
    futures_expiry: date | None = None
    futures_identity_verified: bool = False
    expiry_instant_verified: bool = False
    rate_convention: str = "CONTINUOUS_DECIMAL_PER_YEAR"
    day_count: str = "ACT_365_CALENDAR_SECONDS"
    premium_unit: str = "UNSPECIFIED"
    schema_version: str = "X6_PRICING_CONTEXT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKET_EXCHANGES or self.model != MODEL_BY_MARKET[self.market]:
            raise ValueError("Model must match the exact five-market identity")
        if not isinstance(self.option_expiry, date) or isinstance(self.option_expiry, datetime):
            raise ValueError("Option expiry must be a calendar date")
        if not _aware(self.as_of) or not _text(self.expiry_source_id):
            raise ValueError("Aware as-of time and expiry provenance required")
        if self.option_expiry_at is not None and (
            not _aware(self.option_expiry_at)
            or self.option_expiry_at.astimezone(IST).date() != self.option_expiry
        ):
            raise ValueError("Expiry instant must match the option expiry date in IST")
        if type(self.expiry_instant_verified) is not bool or (
            self.expiry_instant_verified and self.option_expiry_at is None
        ):
            raise ValueError("Verified expiry requires an exact expiry instant")
        if not _text(self.reference_source_id) or self.reference_unit != PRICE_UNITS[self.market]:
            raise ValueError("Exact market price unit and reference provenance required")
        if self.reference_price is not None and not _number(self.reference_price, positive=True):
            raise ValueError("Reference price must be finite and positive")
        if type(self.reference_verified) is not bool or (
            self.reference_verified and self.reference_price is None
        ):
            raise ValueError("Verified reference must include a price")
        if self.annual_risk_free_rate is not None and (
            not _number(self.annual_risk_free_rate, signed=True)
            or abs(self.annual_risk_free_rate) > 1
        ):
            raise ValueError("Annual rate must be finite decimal in [-1, 1]")
        if self.rate_source_id is not None and not _text(self.rate_source_id):
            raise ValueError("Invalid rate provenance")
        if type(self.rate_verified) is not bool or (
            self.rate_verified
            and (self.annual_risk_free_rate is None or not _text(self.rate_source_id))
        ):
            raise ValueError("Verified discount rate requires value and provenance")
        if self.annual_dividend_yield is not None and (
            not _number(self.annual_dividend_yield, signed=True)
            or abs(self.annual_dividend_yield) > 1
        ):
            raise ValueError("Dividend yield must be finite decimal in [-1, 1]")
        if self.dividend_source_id is not None and not _text(self.dividend_source_id):
            raise ValueError("Invalid dividend provenance")
        if type(self.dividend_verified) is not bool or (
            self.dividend_verified
            and (self.annual_dividend_yield is None or not _text(self.dividend_source_id))
        ):
            raise ValueError("Verified yield requires value and provenance")
        if type(self.futures_identity_verified) is not bool:
            raise ValueError("Futures identity flag must be boolean")
        if self.model == "BLACK_SCHOLES_SPOT":
            if (
                self.futures_contract_id is not None
                or self.futures_expiry is not None
                or self.futures_identity_verified
            ):
                raise ValueError("Spot index context must not contain futures identity")
        else:
            if (
                self.annual_dividend_yield is not None
                or self.dividend_source_id is not None
                or self.dividend_verified
            ):
                raise ValueError("Black-76 forward price must not receive a dividend yield")
            if self.futures_contract_id is not None and not _text(self.futures_contract_id):
                raise ValueError("Invalid futures contract identity")
            if self.futures_expiry is not None and (
                not isinstance(self.futures_expiry, date)
                or isinstance(self.futures_expiry, datetime)
                or self.futures_expiry < self.option_expiry
            ):
                raise ValueError("Underlying futures expiry must follow option expiry")
            if self.futures_identity_verified and (
                not _text(self.futures_contract_id) or self.futures_expiry is None
            ):
                raise ValueError("Verified Black-76 needs exact underlying futures identity")
        if (
            self.rate_convention != "CONTINUOUS_DECIMAL_PER_YEAR"
            or self.day_count != "ACT_365_CALENDAR_SECONDS"
            or self.premium_unit != PRICE_UNITS[self.market]
        ):
            raise ValueError("Model units and conventions cannot be changed")
        _disabled_authority(self, "X6_PRICING_CONTEXT_V1")

    def time_to_expiry_years(self) -> float | None:
        """ACT/365 from verified absolute timestamps; never assume a closing hour."""
        if self.option_expiry_at is None or not self.expiry_instant_verified:
            return None
        return (self.option_expiry_at - self.as_of).total_seconds() / _YEAR_SECONDS


@dataclass(frozen=True, slots=True)
class X6OptionInputV1:
    canonical_option_id: str
    source_record_id: str
    option_type: str
    strike: float
    observed_at: datetime
    premium: float | None = None
    premium_source: str = "NONE"  # LTP, MID, NONE; never executable quote
    premium_verified: bool = False
    schema_version: str = "X6_OPTION_INPUT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not all(_text(x) for x in (self.canonical_option_id, self.source_record_id)):
            raise ValueError("Option and source IDs are required")
        if self.option_type not in ("CE", "PE") or not _number(self.strike, positive=True):
            raise ValueError("Option side and strike are invalid")
        if not _aware(self.observed_at):
            raise ValueError("Observation timestamp must be aware")
        if self.premium is not None and not _number(self.premium):
            raise ValueError("Premium must be finite and nonnegative")
        if self.premium_source not in ("LTP", "MID", "NONE"):
            raise ValueError("Unknown premium source")
        if (self.premium is None) != (self.premium_source == "NONE"):
            raise ValueError("Premium and its source must be present together")
        if type(self.premium_verified) is not bool or (
            self.premium_verified and self.premium is None
        ):
            raise ValueError("Verified premium requires a value")
        _disabled_authority(self, "X6_OPTION_INPUT_V1")


@dataclass(frozen=True, slots=True)
class X6VolatilityCaptureV1:
    context: X6PricingContextV1
    session_id: str
    capture_id: str
    source_x5_capture_sha256: str
    observations: tuple[X6OptionInputV1, ...]
    point_in_time_verified: bool = False
    schema_version: str = "X6_VOLATILITY_CAPTURE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.context, X6PricingContextV1):
            raise ValueError("X6 capture requires an immutable X6 pricing context")
        if (
            not _text(self.session_id)
            or not _text(self.capture_id)
            or not _sha(self.source_x5_capture_sha256)
        ):
            raise ValueError("Exact session/capture identity and X5 SHA-256 are required")
        if type(self.observations) is not tuple or any(
            not isinstance(row, X6OptionInputV1) for row in self.observations
        ):
            raise ValueError("Option inputs must be an immutable tuple")
        if type(self.point_in_time_verified) is not bool:
            raise ValueError("Point-in-time flag must be boolean")
        seen_ids: set[str] = set()
        seen_keys: set[tuple[float, str]] = set()
        seen_sources: set[str] = set()
        for row in self.observations:
            key = (float(row.strike), row.option_type)
            if (
                row.canonical_option_id in seen_ids
                or row.source_record_id in seen_sources
                or key in seen_keys
                or row.observed_at > self.context.as_of
            ):
                raise ValueError("Duplicate, inconsistent or future-dated option input")
            seen_ids.add(row.canonical_option_id)
            seen_sources.add(row.source_record_id)
            seen_keys.add(key)
        object.__setattr__(
            self,
            "observations",
            tuple(sorted(self.observations, key=lambda row: (float(row.strike), row.option_type))),
        )
        _disabled_authority(self, "X6_VOLATILITY_CAPTURE_V1")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class X6InputValidationV1:
    market: str
    capture_id: str
    as_of: datetime
    model_status: str
    premium_status: str
    time_status: str
    status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_capture_sha256: str
    source_x5_capture_sha256: str
    schema_version: str = "X6_INPUT_VALIDATION_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKET_EXCHANGES
            or not _text(self.capture_id)
            or not _aware(self.as_of)
        ):
            raise ValueError("Invalid validation identity")
        if (
            self.model_status not in ("AVAILABLE", "UNAVAILABLE")
            or self.premium_status not in ("AVAILABLE", "UNAVAILABLE")
            or self.time_status not in ("POINT_IN_TIME", "RETROSPECTIVE")
        ):
            raise ValueError("Invalid validation component status")
        if self.status not in ("AVAILABLE", "PARTIAL", "UNAVAILABLE"):
            raise ValueError("Invalid aggregate validation status")
        if not _sha(self.source_capture_sha256) or not _sha(self.source_x5_capture_sha256):
            raise ValueError("Source hashes must be canonical SHA-256")
        if (
            type(self.blockers) is not tuple
            or type(self.warnings) is not tuple
            or any(not _text(x) for x in self.blockers + self.warnings)
        ):
            raise ValueError("Invalid validation diagnostics")
        if self.model_status == "UNAVAILABLE" and self.status == "AVAILABLE":
            raise ValueError("Unavailable model cannot be available overall")
        if self.premium_status == "UNAVAILABLE" and self.status == "AVAILABLE":
            raise ValueError("Unavailable premiums cannot be available overall")
        if self.time_status == "RETROSPECTIVE" and self.status == "AVAILABLE":
            raise ValueError("Retrospective input cannot claim real-time availability")
        _disabled_authority(self, "X6_INPUT_VALIDATION_V1")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())
