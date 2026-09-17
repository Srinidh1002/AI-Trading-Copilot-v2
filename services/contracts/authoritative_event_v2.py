"""Provider-neutral contracts for authoritative market events.

No network access, trading decision, strategy weighting, order authority,
or certification credit exists in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from services.core.five_market_universe_v2 import (
    get_target_market,
)


SOURCE_CLASSES = frozenset(
    {
        "CENTRAL_BANK",
        "GOVERNMENT_STATISTICS",
        "REGULATOR",
        "EXCHANGE",
        "COMPANY_EXCHANGE_DISCLOSURE",
        "ENERGY_STATISTICS",
        "DERIVATIVES_REGULATOR",
        "INTERNATIONAL_ORGANIZATION",
        "GOVERNMENT_POLICY",
    }
)

EVENT_TYPES = frozenset(
    {
        "CENTRAL_BANK_POLICY",
        "CENTRAL_BANK_MINUTES",
        "CENTRAL_BANK_SPEECH",
        "INFLATION_RELEASE",
        "GDP_RELEASE",
        "INDUSTRIAL_PRODUCTION",
        "EMPLOYMENT_RELEASE",
        "EXCHANGE_CIRCULAR",
        "REGULATORY_CIRCULAR",
        "COMPANY_DISCLOSURE",
        "EARNINGS_RESULT",
        "CORPORATE_ACTION",
        "INDEX_REBALANCE",
        "TRADING_HOLIDAY",
        "CONTRACT_SPEC_CHANGE",
        "POSITION_LIMIT_CHANGE",
        "SURVEILLANCE_ACTION",
        "COMMODITY_INVENTORY",
        "NATGAS_STORAGE",
        "OIL_MARKET_REPORT",
        "POSITIONING_REPORT",
        "TAX_DUTY_POLICY",
        "IMPORT_EXPORT_POLICY",
        "GOVERNMENT_NOTICE",
        "OTHER_OFFICIAL",
    }
)

EVENT_SEVERITIES = frozenset(
    {
        "INFO",
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }
)

EVENT_PHASES = frozenset(
    {
        "SCHEDULED",
        "APPROACHING",
        "IMMINENT",
        "AWAITING_RELEASE",
        "RELEASED",
        "PRICE_DISCOVERY",
        "STABILIZING",
        "RESOLVED",
        "OBSERVED",
    }
)


def _text(
    value: object,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    return value or None


def _token(
    value: object,
) -> str:
    text = _text(
        value
    )

    if text is None:
        return ""

    return "_".join(
        text.upper().split()
    )


def _aware(
    value: object,
) -> bool:
    return (
        isinstance(
            value,
            datetime,
        )
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _canonical_markets(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(
        values,
        tuple,
    ):
        raise ValueError(
            "Market collection must be a tuple."
        )

    canonical = tuple(
        get_target_market(
            value
        ).symbol
        for value in values
    )

    if len(
        set(
            canonical
        )
    ) != len(
        canonical
    ):
        raise ValueError(
            "Duplicate target markets are not allowed."
        )

    return canonical


def _https_url(
    value: object,
) -> str:
    text = _text(
        value
    )

    if text is None:
        raise ValueError(
            "Official URL is required."
        )

    parsed = urlparse(
        text
    )

    if (
        parsed.scheme.lower()
        != "https"
        or not parsed.netloc
    ):
        raise ValueError(
            "Official URL must use HTTPS."
        )

    return text


@dataclass(frozen=True, slots=True)
class AuthoritativeEventSourceV2:
    source_id: str
    display_name: str
    source_class: str
    jurisdiction: str

    domain: str
    official_url: str

    supported_event_types: tuple[str, ...]
    default_markets: tuple[str, ...] = ()

    schedule_capability: bool = False
    publication_capability: bool = True
    authoritative: bool = True

    schema_version: str = (
        "authoritative_event_source.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        source_id = _token(
            self.source_id
        )

        display_name = _text(
            self.display_name
        )

        source_class = _token(
            self.source_class
        )

        jurisdiction = _token(
            self.jurisdiction
        )

        domain = (
            _text(
                self.domain
            )
            or ""
        ).lower()

        official_url = _https_url(
            self.official_url
        )

        if not source_id:
            raise ValueError(
                "source_id is required."
            )

        if display_name is None:
            raise ValueError(
                "display_name is required."
            )

        if (
            source_class
            not in SOURCE_CLASSES
        ):
            raise ValueError(
                "Unsupported authoritative source class."
            )

        if not jurisdiction:
            raise ValueError(
                "jurisdiction is required."
            )

        if not domain:
            raise ValueError(
                "domain is required."
            )

        host = (
            urlparse(
                official_url
            )
            .netloc
            .lower()
            .split(":")[0]
        )

        if not (
            host == domain
            or host.endswith(
                "." + domain
            )
        ):
            raise ValueError(
                "Official URL domain mismatch."
            )

        if self.authoritative is not True:
            raise ValueError(
                "Authoritative source contract requires authoritative=True."
            )

        if not isinstance(
            self.schedule_capability,
            bool,
        ):
            raise ValueError(
                "schedule_capability must be boolean."
            )

        if not isinstance(
            self.publication_capability,
            bool,
        ):
            raise ValueError(
                "publication_capability must be boolean."
            )

        if not isinstance(
            self.supported_event_types,
            tuple,
        ):
            raise ValueError(
                "supported_event_types must be a tuple."
            )

        normalized_types = tuple(
            _token(
                value
            )
            for value in self.supported_event_types
        )

        if not normalized_types:
            raise ValueError(
                "At least one event type is required."
            )

        if any(
            event_type
            not in EVENT_TYPES
            for event_type in normalized_types
        ):
            raise ValueError(
                "Unsupported event type in source contract."
            )

        if len(
            set(
                normalized_types
            )
        ) != len(
            normalized_types
        ):
            raise ValueError(
                "Duplicate source event types are not allowed."
            )

        default_markets = (
            _canonical_markets(
                self.default_markets
            )
        )

        if (
            self.schema_version
            != "authoritative_event_source.v2"
        ):
            raise ValueError(
                "Invalid authoritative source schema."
            )

        object.__setattr__(
            self,
            "source_id",
            source_id,
        )

        object.__setattr__(
            self,
            "display_name",
            display_name,
        )

        object.__setattr__(
            self,
            "source_class",
            source_class,
        )

        object.__setattr__(
            self,
            "jurisdiction",
            jurisdiction,
        )

        object.__setattr__(
            self,
            "domain",
            domain,
        )

        object.__setattr__(
            self,
            "official_url",
            official_url,
        )

        object.__setattr__(
            self,
            "supported_event_types",
            normalized_types,
        )

        object.__setattr__(
            self,
            "default_markets",
            default_markets,
        )


@dataclass(frozen=True, slots=True)
class AuthoritativeMarketEventV2:
    event_id: str
    event_group_id: str

    source_id: str
    source_event_id: str | None

    title: str
    event_type: str
    severity: str
    jurisdiction: str

    affected_markets: tuple[str, ...]
    affected_symbols: tuple[str, ...]

    observed_at: datetime

    scheduled: bool = False
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    effective_at: datetime | None = None

    source_url: str | None = None

    schema_version: str = (
        "authoritative_market_event.v2"
    )

    def __post_init__(
        self,
    ) -> None:
        event_id = _text(
            self.event_id
        )

        event_group_id = _text(
            self.event_group_id
        )

        source_id = _token(
            self.source_id
        )

        source_event_id = _text(
            self.source_event_id
        )

        title = _text(
            self.title
        )

        event_type = _token(
            self.event_type
        )

        severity = _token(
            self.severity
        )

        jurisdiction = _token(
            self.jurisdiction
        )

        if event_id is None:
            raise ValueError(
                "event_id is required."
            )

        if event_group_id is None:
            raise ValueError(
                "event_group_id is required."
            )

        if not source_id:
            raise ValueError(
                "source_id is required."
            )

        if title is None:
            raise ValueError(
                "title is required."
            )

        if event_type not in EVENT_TYPES:
            raise ValueError(
                "Unsupported event type."
            )

        if severity not in EVENT_SEVERITIES:
            raise ValueError(
                "Unsupported event severity."
            )

        if not jurisdiction:
            raise ValueError(
                "jurisdiction is required."
            )

        markets = _canonical_markets(
            self.affected_markets
        )

        if not markets:
            raise ValueError(
                "At least one affected market is required."
            )

        if not isinstance(
            self.affected_symbols,
            tuple,
        ):
            raise ValueError(
                "affected_symbols must be a tuple."
            )

        symbols = tuple(
            value
            for value in (
                _text(
                    symbol
                )
                for symbol in self.affected_symbols
            )
            if value is not None
        )

        if len(
            symbols
        ) != len(
            self.affected_symbols
        ):
            raise ValueError(
                "affected_symbols contains an invalid value."
            )

        if len(
            set(
                symbols
            )
        ) != len(
            symbols
        ):
            raise ValueError(
                "Duplicate affected symbols are not allowed."
            )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "observed_at must be timezone-aware."
            )

        if not isinstance(
            self.scheduled,
            bool,
        ):
            raise ValueError(
                "scheduled must be boolean."
            )

        if self.scheduled:
            if not _aware(
                self.scheduled_at
            ):
                raise ValueError(
                    "Scheduled event requires timezone-aware scheduled_at."
                )
        elif self.scheduled_at is not None:
            raise ValueError(
                "Unscheduled event cannot carry scheduled_at."
            )

        for name, value in (
            (
                "published_at",
                self.published_at,
            ),
            (
                "effective_at",
                self.effective_at,
            ),
        ):
            if (
                value is not None
                and not _aware(
                    value
                )
            ):
                raise ValueError(
                    f"{name} must be timezone-aware when present."
                )

        source_url = None

        if self.source_url is not None:
            source_url = _https_url(
                self.source_url
            )

        if (
            self.schema_version
            != "authoritative_market_event.v2"
        ):
            raise ValueError(
                "Invalid authoritative event schema."
            )

        object.__setattr__(
            self,
            "event_id",
            event_id,
        )

        object.__setattr__(
            self,
            "event_group_id",
            event_group_id,
        )

        object.__setattr__(
            self,
            "source_id",
            source_id,
        )

        object.__setattr__(
            self,
            "source_event_id",
            source_event_id,
        )

        object.__setattr__(
            self,
            "title",
            title,
        )

        object.__setattr__(
            self,
            "event_type",
            event_type,
        )

        object.__setattr__(
            self,
            "severity",
            severity,
        )

        object.__setattr__(
            self,
            "jurisdiction",
            jurisdiction,
        )

        object.__setattr__(
            self,
            "affected_markets",
            markets,
        )

        object.__setattr__(
            self,
            "affected_symbols",
            symbols,
        )

        object.__setattr__(
            self,
            "source_url",
            source_url,
        )
