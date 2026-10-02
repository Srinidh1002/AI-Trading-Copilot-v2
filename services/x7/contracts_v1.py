"""Immutable, provider-neutral X7 external-context capture contracts.

Records *supplied* global, institutional and scheduled-event facts. It does not
fetch facts, establish provider authenticity, infer direction or block trades.
All source verification fields represent caller assertions, not independent
proof. Absent values and unavailable-at-the-time evidence stay unavailable.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from hashlib import sha256

MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")
INDEX_MARKETS = frozenset({"NIFTY", "SENSEX"})
MARKET_EXCHANGES = {
    "NIFTY": "NFO",
    "SENSEX": "BFO",
    "CRUDEOILM": "MCX",
    "GOLDM": "MCX",
    "NATGASMINI": "MCX",
}
# Controlled names/types. Historical index closes are NOT live index futures.
GLOBAL_TYPES = {
    "GIFT_NIFTY": "INDEX_FUTURE",
    "SP500": "INDEX_CLOSE",
    "NASDAQ": "INDEX_CLOSE",
    "DOW_JONES": "INDEX_CLOSE",
    "NIKKEI_225": "INDEX_CLOSE",
    "HANG_SENG": "INDEX_CLOSE",
    "SHANGHAI_COMPOSITE": "INDEX_CLOSE",
    "DXY": "FX_INDEX",
    "USD_INR": "FX_RATE",
    "BRENT_CRUDE": "COMMODITY_PRICE",
    "WTI_CRUDE": "COMMODITY_PRICE",
    "US_10Y_YIELD": "BOND_YIELD",
    "INDIA_10Y_YIELD": "BOND_YIELD",
    "INDIA_VIX": "VOLATILITY_INDEX",
}
GLOBAL_UNITS = {
    "GIFT_NIFTY": "INDEX_POINTS",
    "SP500": "INDEX_POINTS",
    "NASDAQ": "INDEX_POINTS",
    "DOW_JONES": "INDEX_POINTS",
    "NIKKEI_225": "INDEX_POINTS",
    "HANG_SENG": "INDEX_POINTS",
    "SHANGHAI_COMPOSITE": "INDEX_POINTS",
    "DXY": "INDEX_POINTS",
    "USD_INR": "INR_PER_USD",
    "BRENT_CRUDE": "USD_PER_BARREL",
    "WTI_CRUDE": "USD_PER_BARREL",
    "US_10Y_YIELD": "PERCENT_PER_YEAR",
    "INDIA_10Y_YIELD": "PERCENT_PER_YEAR",
    "INDIA_VIX": "PERCENT_ANNUALIZED",
}
SESSION_REFERENCES = frozenset(
    {"PREVIOUS_CLOSE", "PREMARKET", "CURRENT_SESSION", "OVERNIGHT", "DELAYED", "UNKNOWN"}
)
EVIDENCE_STATUSES = frozenset({"AVAILABLE", "UNVERIFIED", "UNAVAILABLE", "STALE"})
EVENT_CATEGORIES = frozenset(
    {
        "RBI_POLICY",
        "CPI",
        "WPI",
        "GDP",
        "UNION_BUDGET",
        "ELECTION",
        "EXCHANGE_HOLIDAY",
        "SPECIAL_SESSION",
        "WEEKLY_EXPIRY",
        "MONTHLY_EXPIRY",
        "ROLLOVER",
        "OTHER_SCHEDULED_MACRO",
    }
)
SEVERITIES = frozenset({"LOW", "MODERATE", "HIGH", "EXTREME", "UNKNOWN"})


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
        and all(char in "0123456789abcdef" for char in value)
    )


def _markets(values: object, *, allow_empty: bool = False) -> bool:
    return (
        type(values) is tuple
        and (allow_empty or len(values) > 0)
        and all(value in MARKETS for value in values)
        and len(set(values)) == len(values)
        and tuple(sorted(values, key=MARKETS.index)) == values
    )


def _encode(value: object) -> object:
    if isinstance(value, datetime) or isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_encode(v) for v in value]
    return value


def canonical_sha256(value: object) -> str:
    return sha256(
        json.dumps(_encode(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    ).hexdigest()


def _authority(obj: object, schema: str) -> None:
    if (
        getattr(obj, "schema_version") != schema
        or getattr(obj, "data_only") is not True
        or getattr(obj, "independent_vote") is not False
        or any(
            getattr(obj, name) is not False
            for name in (
                "execution_authority",
                "risk_authority",
                "position_authority",
                "certification_authority",
                "live_execution_eligible",
            )
        )
    ):
        raise ValueError("X7 schema and zero-authority flags are fixed")


def _source(
    *,
    source_id: str,
    observed_at: datetime,
    published_at: datetime | None,
    available_at: datetime | None,
    source_verified: bool,
) -> None:
    if not _text(source_id) or not _aware(observed_at):
        raise ValueError("Source identity and aware observation time are mandatory")
    if published_at is not None and (not _aware(published_at) or published_at < observed_at):
        raise ValueError("Publication must not precede the observation")
    if available_at is not None and (
        not _aware(available_at) or published_at is None or available_at < published_at
    ):
        raise ValueError("Availability must not precede a known publication")
    if type(source_verified) is not bool:
        raise ValueError("Source verification must be an exact boolean")
    if source_verified and (published_at is None or available_at is None):
        raise ValueError("Verified source needs publication and availability evidence")


@dataclass(frozen=True, slots=True)
class X7GlobalObservationV1:
    name: str
    observation_type: str
    unit: str
    session_reference: str
    source_id: str
    observed_at: datetime
    published_at: datetime | None
    available_at: datetime | None
    source_verified: bool
    value: float | None
    value_verified: bool
    previous_value: float | None = None
    status: str = "UNVERIFIED"
    source_record_id: str | None = None
    schema_version: str = "X7_GLOBAL_OBSERVATION_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.name not in GLOBAL_TYPES
            or self.observation_type != GLOBAL_TYPES[self.name]
            or self.unit != GLOBAL_UNITS[self.name]
            or self.session_reference not in SESSION_REFERENCES
        ):
            raise ValueError("Unknown or mismatched global identity, type, unit or session")
        _source(
            source_id=self.source_id,
            observed_at=self.observed_at,
            published_at=self.published_at,
            available_at=self.available_at,
            source_verified=self.source_verified,
        )
        if self.source_record_id is not None and not _text(self.source_record_id):
            raise ValueError("Invalid source record identity")
        if self.value is not None and not _number(
            self.value,
            positive=self.observation_type != "BOND_YIELD",
            signed=self.observation_type == "BOND_YIELD",
        ):
            raise ValueError("Observed global value must be finite and positive")
        if self.previous_value is not None and not _number(
            self.previous_value,
            positive=self.observation_type != "BOND_YIELD",
            signed=self.observation_type == "BOND_YIELD",
        ):
            raise ValueError("Previous global value must be finite and positive")
        if type(self.value_verified) is not bool or (
            self.value_verified and (self.value is None or not self.source_verified)
        ):
            raise ValueError("Verified value needs a verified source and a value")
        if self.status not in EVIDENCE_STATUSES:
            raise ValueError("Unknown evidence status")
        if self.status == "AVAILABLE" and (
            not self.source_verified
            or not self.value_verified
            or self.value is None
            or not _text(self.source_record_id)
        ):
            raise ValueError("Available evidence must be verified")
        if self.status == "UNAVAILABLE" and (self.value is not None or self.value_verified):
            raise ValueError("Unavailable value cannot carry a number")
        if self.status == "UNVERIFIED" and self.value_verified:
            raise ValueError("Unverified or stale evidence cannot claim a verified value")
        _authority(self, "X7_GLOBAL_OBSERVATION_V1")


@dataclass(frozen=True, slots=True)
class X7InstitutionalFlowV1:
    """India cash-equity flows; not directly attributed to MCX commodities."""

    trading_date: date
    applicable_markets: tuple[str, ...]
    flow_unit: str
    source_id: str
    observed_at: datetime
    published_at: datetime | None
    available_at: datetime | None
    source_verified: bool
    fii_net: float | None
    dii_net: float | None
    values_verified: bool
    publication_state: str = "UNAVAILABLE"
    status: str = "UNVERIFIED"
    schema_version: str = "X7_INSTITUTIONAL_FLOW_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.trading_date, date) or isinstance(self.trading_date, datetime):
            raise ValueError("Trading date must be a date")
        if not _markets(self.applicable_markets) or any(
            market not in INDEX_MARKETS for market in self.applicable_markets
        ):
            raise ValueError("India cash flow applicability must be explicit index markets")
        if self.flow_unit != "CRORE_INR":
            raise ValueError("No inferred cash-flow unit conversion")
        _source(
            source_id=self.source_id,
            observed_at=self.observed_at,
            published_at=self.published_at,
            available_at=self.available_at,
            source_verified=self.source_verified,
        )
        if self.observed_at.date() < self.trading_date:
            raise ValueError("Flow observation cannot precede the trading date")
        if self.fii_net is not None and not _number(self.fii_net, signed=True):
            raise ValueError("FII cash flow must be finite and signed")
        if self.dii_net is not None and not _number(self.dii_net, signed=True):
            raise ValueError("DII cash flow must be finite and signed")
        if type(self.values_verified) is not bool or (
            self.values_verified
            and (not self.source_verified or (self.fii_net is None and self.dii_net is None))
        ):
            raise ValueError("Verified flow requires a source and a reported value")
        if self.publication_state not in {"FINAL", "PROVISIONAL", "UNAVAILABLE"}:
            raise ValueError("Unknown flow publication state")
        if self.status not in EVIDENCE_STATUSES:
            raise ValueError("Unknown flow status")
        if self.status == "AVAILABLE" and (
            not self.values_verified or self.publication_state != "FINAL"
        ):
            raise ValueError("Available institutional flow must be verified and final")
        if self.status == "UNAVAILABLE" and (
            self.fii_net is not None or self.dii_net is not None or self.values_verified
        ):
            raise ValueError("Unavailable flows must not carry numeric values")
        if self.status == "UNVERIFIED" and self.values_verified:
            raise ValueError("Unverified or stale flow cannot be verified")
        _authority(self, "X7_INSTITUTIONAL_FLOW_V1")


@dataclass(frozen=True, slots=True)
class X7ScheduledEventV1:
    event_id: str
    category: str
    scheduled_at: datetime
    affected_markets: tuple[str, ...]
    severity: str
    source_id: str
    observed_at: datetime
    published_at: datetime | None
    available_at: datetime | None
    source_verified: bool
    confirmed: bool
    status: str = "UNVERIFIED"
    schema_version: str = "X7_SCHEDULED_EVENT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not _text(self.event_id)
            or self.category not in EVENT_CATEGORIES
            or not _aware(self.scheduled_at)
            or not _markets(self.affected_markets)
            or self.severity not in SEVERITIES
        ):
            raise ValueError("Invalid scheduled-event identity, category or applicability")
        _source(
            source_id=self.source_id,
            observed_at=self.observed_at,
            published_at=self.published_at,
            available_at=self.available_at,
            source_verified=self.source_verified,
        )
        if type(self.confirmed) is not bool:
            raise ValueError("Event confirmation must be an exact boolean")
        if self.status not in EVIDENCE_STATUSES:
            raise ValueError("Invalid event status")
        if self.status == "AVAILABLE" and (
            not self.confirmed or not self.source_verified or self.severity == "UNKNOWN"
        ):
            raise ValueError("Available event needs verified confirmation and severity")
        if self.status in {"UNVERIFIED", "UNAVAILABLE"} and self.confirmed:
            raise ValueError("Unverified or stale event cannot claim confirmed")
        _authority(self, "X7_SCHEDULED_EVENT_V1")


@dataclass(frozen=True, slots=True)
class X7ContextCaptureV1:
    market: str
    session_id: str
    capture_id: str
    as_of: datetime
    global_observations: tuple[X7GlobalObservationV1, ...]
    institutional_flows: tuple[X7InstitutionalFlowV1, ...]
    scheduled_events: tuple[X7ScheduledEventV1, ...]
    capture_verified: bool
    point_in_time_verified: bool
    historical_retrieval: bool
    schema_version: str = "X7_CONTEXT_CAPTURE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MARKETS or not _text(self.session_id) or not _text(self.capture_id):
            raise ValueError("Exact five-market and session/capture identities required")
        if not _aware(self.as_of):
            raise ValueError("Capture as_of must be aware")
        for name, cls in (
            ("global_observations", X7GlobalObservationV1),
            ("institutional_flows", X7InstitutionalFlowV1),
            ("scheduled_events", X7ScheduledEventV1),
        ):
            rows = getattr(self, name)
            if type(rows) is not tuple or any(not isinstance(row, cls) for row in rows):
                raise ValueError(f"{name} must be a tuple of exact contracts")
        if len({row.name for row in self.global_observations}) != len(self.global_observations):
            raise ValueError("Duplicate global observation names")
        if len({row.trading_date for row in self.institutional_flows}) != len(
            self.institutional_flows
        ):
            raise ValueError("Duplicate institutional trading dates")
        if len({row.event_id for row in self.scheduled_events}) != len(self.scheduled_events):
            raise ValueError("Duplicate scheduled-event IDs")
        if any(self.market not in row.applicable_markets for row in self.institutional_flows):
            raise ValueError("Institutional flow does not apply to the target market")
        if any(self.market not in row.affected_markets for row in self.scheduled_events):
            raise ValueError("Scheduled event does not apply to target market")
        if any(
            type(flag) is not bool
            for flag in (
                self.capture_verified,
                self.point_in_time_verified,
                self.historical_retrieval,
            )
        ):
            raise ValueError("Capture verification flags must be exact booleans")
        if self.point_in_time_verified and (not self.capture_verified or self.historical_retrieval):
            raise ValueError("Retrospective/unverified capture cannot be point-in-time")
        if self.point_in_time_verified:
            for row in (
                *self.global_observations,
                *self.institutional_flows,
                *self.scheduled_events,
            ):
                if (
                    not row.source_verified
                    or row.available_at is None
                    or row.available_at > self.as_of
                ):
                    raise ValueError("Point-in-time capture includes unproven/future availability")
        _authority(self, "X7_CONTEXT_CAPTURE_V1")

    def to_dict(self) -> dict[str, object]:
        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class X7ContextValidationV1:
    market: str
    capture_id: str
    as_of: datetime
    status: str
    global_status: str
    institutional_status: str
    event_status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_capture_sha256: str
    schema_version: str = "X7_CONTEXT_VALIDATION_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKETS
            or not _text(self.capture_id)
            or not _aware(self.as_of)
            or self.status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}
            or any(
                state not in {"AVAILABLE", "UNAVAILABLE"}
                for state in (self.global_status, self.institutional_status, self.event_status)
            )
            or type(self.blockers) is not tuple
            or type(self.warnings) is not tuple
            or any(not _text(item) for item in (*self.blockers, *self.warnings))
            or len(set(self.blockers)) != len(self.blockers)
            or len(set(self.warnings)) != len(self.warnings)
            or not _sha(self.source_capture_sha256)
        ):
            raise ValueError("Invalid X7 validation summary")
        if self.status == "AVAILABLE" and (
            self.blockers
            or self.warnings
            or any(
                state != "AVAILABLE"
                for state in (self.global_status, self.institutional_status, self.event_status)
            )
        ):
            raise ValueError("Fully available validation must have three complete families")
        if self.status == "UNAVAILABLE" and not self.blockers:
            raise ValueError("Unavailable validation requires explicit blockers")
        _authority(self, "X7_CONTEXT_VALIDATION_V1")

    def to_dict(self) -> dict[str, object]:
        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())
