"""Source-native NSE/BSE company disclosure candidate contract.

This contract exists before IndianPrimaryNoticeV2.

The exchange feeds inspected by P8C.3C provide useful intraday wall-clock
timestamps, stable exchange identifiers, company/security identity and
source provenance, but they do not currently prove the timezone attached
to those record timestamps.

Therefore:

* source wall-clock values are preserved exactly;
* local datetimes remain timezone-naive;
* no IST/UTC offset is inferred;
* no candidate becomes a NIFTY/SENSEX market event here;
* constituent/index resolution remains a separate downstream boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse


EXCHANGE_DISCLOSURE_SOURCE_IDS = frozenset(
    {
        "NSE",
        "BSE",
    }
)

EXCHANGE_DISCLOSURE_KINDS = frozenset(
    {
        "CORPORATE_ANNOUNCEMENT",
        "CORPORATE_ACTION",
    }
)

EXCHANGE_DISCLOSURE_TIMESTAMP_PRECISIONS = frozenset(
    {
        "LOCAL_DATETIME_NO_ZONE",
    }
)

EXCHANGE_DISCLOSURE_TIMEZONE_STATUSES = frozenset(
    {
        "SOURCE_UNSPECIFIED",
    }
)

EXCHANGE_DISCLOSURE_PRIMARY_TIME_SEMANTICS = frozenset(
    {
        "NSE_AN_DT",
        "BSE_EXCHANGE_RECEIVED_TIME",
    }
)

_SOURCE_DOMAINS = {
    "NSE": "nseindia.com",
    "BSE": "bseindia.com",
}


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()
    return value or None


def _token(value: object) -> str:
    text = _text(value)

    if text is None:
        return ""

    return "_".join(text.upper().split())


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _naive(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and (
            value.tzinfo is None
            or value.utcoffset() is None
        )
    )


def _official_https_url(
    source_id: str,
    value: object,
    *,
    field_name: str,
) -> str:
    text = _text(value)

    if text is None:
        raise ValueError(
            f"{field_name} is required."
        )

    parsed = urlparse(text)

    host = (
        parsed.hostname
        or ""
    ).lower()

    domain = _SOURCE_DOMAINS[source_id]

    if (
        parsed.scheme.lower() != "https"
        or not (
            host == domain
            or host.endswith(
                "." + domain
            )
        )
    ):
        raise ValueError(
            f"{field_name} must use an official "
            f"{source_id} HTTPS domain."
        )

    return text


@dataclass(
    frozen=True,
    slots=True,
)
class ExchangeDisclosureCandidateV2:
    source_id: str
    disclosure_kind: str

    company_name: str
    title: str

    source_item_id: str
    source_url: str

    observed_at: datetime

    raw_primary_time: str
    primary_time_local: datetime
    primary_time_semantics: str

    exchange_symbol: str | None = None
    security_code: str | None = None
    isin: str | None = None

    detail_text: str | None = None
    attachment_url: str | None = None

    raw_disseminated_time: str | None = None
    disseminated_time_local: datetime | None = None

    timestamp_precision: str = (
        "LOCAL_DATETIME_NO_ZONE"
    )

    timezone_status: str = (
        "SOURCE_UNSPECIFIED"
    )

    schema_version: str = (
        "exchange_disclosure_candidate.v2"
    )

    def __post_init__(self) -> None:
        source_id = _token(
            self.source_id
        )

        disclosure_kind = _token(
            self.disclosure_kind
        )

        company_name = _text(
            self.company_name
        )

        title = _text(
            self.title
        )

        source_item_id = _text(
            self.source_item_id
        )

        raw_primary_time = _text(
            self.raw_primary_time
        )

        primary_semantics = _token(
            self.primary_time_semantics
        )

        exchange_symbol = _text(
            self.exchange_symbol
        )

        security_code = _text(
            self.security_code
        )

        isin = _text(
            self.isin
        )

        detail_text = _text(
            self.detail_text
        )

        raw_disseminated_time = _text(
            self.raw_disseminated_time
        )

        precision = _token(
            self.timestamp_precision
        )

        timezone_status = _token(
            self.timezone_status
        )

        if (
            source_id
            not in EXCHANGE_DISCLOSURE_SOURCE_IDS
        ):
            raise ValueError(
                "Unsupported exchange disclosure source."
            )

        if (
            disclosure_kind
            not in EXCHANGE_DISCLOSURE_KINDS
        ):
            raise ValueError(
                "Unsupported exchange disclosure kind."
            )

        if company_name is None:
            raise ValueError(
                "company_name is required."
            )

        if title is None:
            raise ValueError(
                "title is required."
            )

        if source_item_id is None:
            raise ValueError(
                "source_item_id is required."
            )

        source_url = _official_https_url(
            source_id,
            self.source_url,
            field_name="source_url",
        )

        if not _aware(
            self.observed_at
        ):
            raise ValueError(
                "observed_at must be timezone-aware."
            )

        if raw_primary_time is None:
            raise ValueError(
                "raw_primary_time is required."
            )

        if not _naive(
            self.primary_time_local
        ):
            raise ValueError(
                "primary_time_local must remain "
                "timezone-naive."
            )

        if (
            primary_semantics
            not in EXCHANGE_DISCLOSURE_PRIMARY_TIME_SEMANTICS
        ):
            raise ValueError(
                "Unsupported primary-time semantics."
            )

        if (
            source_id == "NSE"
            and primary_semantics != "NSE_AN_DT"
        ):
            raise ValueError(
                "NSE candidate must preserve NSE_AN_DT semantics."
            )

        if (
            source_id == "BSE"
            and primary_semantics
            != "BSE_EXCHANGE_RECEIVED_TIME"
        ):
            raise ValueError(
                "BSE candidate must preserve "
                "Exchange Received Time semantics."
            )

        if (
            exchange_symbol is None
            and security_code is None
        ):
            raise ValueError(
                "At least one exchange security identifier "
                "is required."
            )

        if exchange_symbol is not None:
            exchange_symbol = (
                exchange_symbol.upper()
            )

        if isin is not None:
            isin = isin.upper()

        attachment_url = None

        if self.attachment_url is not None:
            attachment_url = (
                _official_https_url(
                    source_id,
                    self.attachment_url,
                    field_name="attachment_url",
                )
            )

        has_raw_dissemination = (
            raw_disseminated_time
            is not None
        )

        has_parsed_dissemination = (
            self.disseminated_time_local
            is not None
        )

        if (
            has_raw_dissemination
            != has_parsed_dissemination
        ):
            raise ValueError(
                "Raw and parsed dissemination time "
                "must be supplied together."
            )

        if (
            self.disseminated_time_local
            is not None
        ):
            if not _naive(
                self.disseminated_time_local
            ):
                raise ValueError(
                    "disseminated_time_local must remain "
                    "timezone-naive."
                )

            if (
                self.disseminated_time_local
                < self.primary_time_local
            ):
                raise ValueError(
                    "Dissemination cannot precede the "
                    "source primary timestamp."
                )

        if (
            precision
            not in
            EXCHANGE_DISCLOSURE_TIMESTAMP_PRECISIONS
        ):
            raise ValueError(
                "Unsupported exchange timestamp precision."
            )

        if (
            timezone_status
            not in
            EXCHANGE_DISCLOSURE_TIMEZONE_STATUSES
        ):
            raise ValueError(
                "Unsupported exchange timezone status."
            )

        if (
            precision
            != "LOCAL_DATETIME_NO_ZONE"
            or timezone_status
            != "SOURCE_UNSPECIFIED"
        ):
            raise ValueError(
                "P8C.3C candidates must not invent "
                "timezone provenance."
            )

        if (
            self.schema_version
            != "exchange_disclosure_candidate.v2"
        ):
            raise ValueError(
                "Invalid exchange disclosure schema."
            )

        object.__setattr__(
            self,
            "source_id",
            source_id,
        )

        object.__setattr__(
            self,
            "disclosure_kind",
            disclosure_kind,
        )

        object.__setattr__(
            self,
            "company_name",
            company_name,
        )

        object.__setattr__(
            self,
            "title",
            title,
        )

        object.__setattr__(
            self,
            "source_item_id",
            source_item_id,
        )

        object.__setattr__(
            self,
            "source_url",
            source_url,
        )

        object.__setattr__(
            self,
            "raw_primary_time",
            raw_primary_time,
        )

        object.__setattr__(
            self,
            "primary_time_semantics",
            primary_semantics,
        )

        object.__setattr__(
            self,
            "exchange_symbol",
            exchange_symbol,
        )

        object.__setattr__(
            self,
            "security_code",
            security_code,
        )

        object.__setattr__(
            self,
            "isin",
            isin,
        )

        object.__setattr__(
            self,
            "detail_text",
            detail_text,
        )

        object.__setattr__(
            self,
            "attachment_url",
            attachment_url,
        )

        object.__setattr__(
            self,
            "raw_disseminated_time",
            raw_disseminated_time,
        )

        object.__setattr__(
            self,
            "timestamp_precision",
            precision,
        )

        object.__setattr__(
            self,
            "timezone_status",
            timezone_status,
        )
