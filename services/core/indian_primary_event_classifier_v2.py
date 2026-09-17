"""Deterministic classification for Indian primary-source notices.

No network access is performed here.

RBI/SEBI/MCX market-wide notices can use catalog market scope.
NSE/BSE company disclosures require explicit symbol-to-index resolution
before an AuthoritativeMarketEventV2 may be created.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
from urllib.parse import urlparse

from services.contracts.authoritative_event_v2 import (
    AuthoritativeMarketEventV2,
)
from services.contracts.indian_primary_notice_v2 import (
    ClassifiedPrimaryNoticeV2,
    IndianPrimaryNoticeV2,
)
from services.core.authoritative_event_source_catalog_v2 import (
    get_authoritative_event_source,
)
from services.core.five_market_universe_v2 import (
    get_target_market,
)


def _normalized_text(
    notice: IndianPrimaryNoticeV2,
) -> str:
    return " ".join(
        (
            notice.title
            + " "
            + (
                notice.detail_text
                or ""
            )
        )
        .lower()
        .split()
    )


def _validate_source_domain(
    notice: IndianPrimaryNoticeV2,
) -> None:
    source = (
        get_authoritative_event_source(
            notice.source_id
        )
    )

    host = (
        urlparse(
            notice.source_url
        )
        .hostname
        or ""
    ).lower()

    domain = (
        source.domain.lower()
    )

    if not (
        host == domain
        or host.endswith(
            "." + domain
        )
    ):
        raise ValueError(
            "Primary notice URL does not match authoritative source domain."
        )


def _classification(
    notice: IndianPrimaryNoticeV2,
    *,
    event_type: str,
    severity: str,
    market_scope_policy: str,
    reason: str,
) -> ClassifiedPrimaryNoticeV2:
    source = (
        get_authoritative_event_source(
            notice.source_id
        )
    )

    if (
        event_type
        not in source.supported_event_types
    ):
        raise ValueError(
            "Classified event type is not supported by source catalog."
        )

    return (
        ClassifiedPrimaryNoticeV2(
            notice=notice,
            event_type=event_type,
            severity=severity,
            market_scope_policy=(
                market_scope_policy
            ),
            classification_reason=(
                reason
            ),
        )
    )


def classify_indian_primary_notice_v2(
    notice: IndianPrimaryNoticeV2,
) -> ClassifiedPrimaryNoticeV2 | None:
    if not isinstance(
        notice,
        IndianPrimaryNoticeV2,
    ):
        raise TypeError(
            "IndianPrimaryNoticeV2 required."
        )

    _validate_source_domain(
        notice
    )

    text = _normalized_text(
        notice
    )

    source_id = (
        notice.source_id
    )

    if source_id == "RBI":
        if (
            "minutes of the monetary policy committee"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "CENTRAL_BANK_MINUTES"
                ),
                severity="MEDIUM",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "RBI_MPC_MINUTES"
                ),
            )

        policy_markers = (
            "monetary policy statement",
            "monetary policy committee meeting",
            "monetary policy committee (mpc)",
            "governor's statement",
            "governor’s statement",
        )

        if any(
            marker in text
            for marker
            in policy_markers
        ):
            return _classification(
                notice,
                event_type=(
                    "CENTRAL_BANK_POLICY"
                ),
                severity="HIGH",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "RBI_MONETARY_POLICY"
                ),
            )

        if (
            "repo rate"
            in text
            and "policy"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "CENTRAL_BANK_POLICY"
                ),
                severity="HIGH",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "RBI_POLICY_RATE"
                ),
            )

        # Penalties, routine auctions and other RBI releases are
        # not automatically promoted to market events.
        return None

    if source_id == "SEBI":
        if (
            "position limit"
            in text
            or "position limits"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "POSITION_LIMIT_CHANGE"
                ),
                severity="HIGH",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "SEBI_POSITION_LIMIT"
                ),
            )

        if (
            "surveillance"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "SURVEILLANCE_ACTION"
                ),
                severity="HIGH",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "SEBI_SURVEILLANCE"
                ),
            )

        if (
            notice.notice_kind
            == "CIRCULAR"
        ):
            return _classification(
                notice,
                event_type=(
                    "REGULATORY_CIRCULAR"
                ),
                severity="MEDIUM",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "SEBI_CIRCULAR"
                ),
            )

        return None

    if source_id == "MCX":
        if (
            "position limit"
            in text
            or "position limits"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "POSITION_LIMIT_CHANGE"
                ),
                severity="HIGH",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "MCX_POSITION_LIMIT"
                ),
            )

        if (
            "surveillance"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "SURVEILLANCE_ACTION"
                ),
                severity="HIGH",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "MCX_SURVEILLANCE"
                ),
            )

        if (
            "trading holiday"
            in text
            or "trading holidays"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "TRADING_HOLIDAY"
                ),
                severity="MEDIUM",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "MCX_TRADING_HOLIDAY"
                ),
            )

        if (
            "contract specification"
            in text
            or "contract launch calendar"
            in text
        ):
            return _classification(
                notice,
                event_type=(
                    "CONTRACT_SPEC_CHANGE"
                ),
                severity="MEDIUM",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "MCX_CONTRACT_CHANGE"
                ),
            )

        if (
            notice.notice_kind
            in {
                "CIRCULAR",
                "EXCHANGE_NOTICE",
            }
        ):
            return _classification(
                notice,
                event_type=(
                    "EXCHANGE_CIRCULAR"
                ),
                severity="INFO",
                market_scope_policy=(
                    "SOURCE_DEFAULT"
                ),
                reason=(
                    "MCX_GENERAL_CIRCULAR"
                ),
            )

        return None

    if source_id in {
        "NSE",
        "BSE",
    }:
        # Exchange-wide index/market notices may use source-default scope.
        if (
            notice.notice_kind
            == "EXCHANGE_NOTICE"
        ):
            if (
                "index rebalance"
                in text
                or "index rebalancing"
                in text
                or "index reconstitution"
                in text
            ):
                return _classification(
                    notice,
                    event_type=(
                        "INDEX_REBALANCE"
                    ),
                    severity="HIGH",
                    market_scope_policy=(
                        "SOURCE_DEFAULT"
                    ),
                    reason=(
                        f"{source_id}_INDEX_REBALANCE"
                    ),
                )

            if (
                "trading holiday"
                in text
                or "trading holidays"
                in text
            ):
                return _classification(
                    notice,
                    event_type=(
                        "TRADING_HOLIDAY"
                    ),
                    severity="MEDIUM",
                    market_scope_policy=(
                        "SOURCE_DEFAULT"
                    ),
                    reason=(
                        f"{source_id}_TRADING_HOLIDAY"
                    ),
                )

            if (
                "position limit"
                in text
                or "position limits"
                in text
            ):
                return _classification(
                    notice,
                    event_type=(
                        "POSITION_LIMIT_CHANGE"
                    ),
                    severity="HIGH",
                    market_scope_policy=(
                        "SOURCE_DEFAULT"
                    ),
                    reason=(
                        f"{source_id}_POSITION_LIMIT"
                    ),
                )

        if (
            notice.notice_kind
            not in {
                "CORPORATE_ANNOUNCEMENT",
                "CORPORATE_ACTION",
            }
        ):
            return None

        # Company-specific exchange filings must carry a symbol and
        # must NOT automatically become NIFTY/SENSEX-wide evidence.
        if not notice.affected_symbols:
            return None

        if (
            notice.notice_kind
            == "CORPORATE_ACTION"
            or any(
                marker in text
                for marker in (
                    "dividend",
                    "bonus",
                    "stock split",
                    "split of shares",
                    "rights issue",
                    "buyback",
                    "record date",
                )
            )
        ):
            return _classification(
                notice,
                event_type=(
                    "CORPORATE_ACTION"
                ),
                severity="MEDIUM",
                market_scope_policy=(
                    "SYMBOL_RESOLUTION_REQUIRED"
                ),
                reason=(
                    f"{source_id}_CORPORATE_ACTION"
                ),
            )

        if any(
            marker in text
            for marker in (
                "financial results",
                "quarterly results",
                "annual results",
                "earnings result",
                "earnings results",
            )
        ):
            return _classification(
                notice,
                event_type=(
                    "EARNINGS_RESULT"
                ),
                severity="MEDIUM",
                market_scope_policy=(
                    "SYMBOL_RESOLUTION_REQUIRED"
                ),
                reason=(
                    f"{source_id}_EARNINGS_RESULT"
                ),
            )

        material_markers = (
            "regulation 30",
            "reg. 30",
            "material issue",
            "material event",
            "credit rating",
            "acquisition",
            "merger",
            "amalgamation",
            "order received",
            "award of order",
            "default",
            "resignation",
            "appointment",
        )

        severity = (
            "MEDIUM"
            if any(
                marker in text
                for marker
                in material_markers
            )
            else "INFO"
        )

        return _classification(
            notice,
            event_type=(
                "COMPANY_DISCLOSURE"
            ),
            severity=severity,
            market_scope_policy=(
                "SYMBOL_RESOLUTION_REQUIRED"
            ),
            reason=(
                f"{source_id}_COMPANY_DISCLOSURE"
            ),
        )

    return None


def _stable_id(
    prefix: str,
    *parts: str,
) -> str:
    digest = (
        hashlib.sha256(
            "|".join(
                parts
            ).encode(
                "utf-8"
            )
        )
        .hexdigest()[:20]
    )

    return (
        f"{prefix}:{digest}"
    )


def build_authoritative_event_from_primary_notice_v2(
    classified: ClassifiedPrimaryNoticeV2,
    *,
    observed_at: datetime,
    resolved_markets: tuple[
        str,
        ...,
    ] = (),
) -> AuthoritativeMarketEventV2 | None:
    if not isinstance(
        classified,
        ClassifiedPrimaryNoticeV2,
    ):
        raise TypeError(
            "ClassifiedPrimaryNoticeV2 required."
        )

    if (
        not isinstance(
            observed_at,
            datetime,
        )
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError(
            "observed_at must be timezone-aware."
        )

    notice = (
        classified.notice
    )

    if (
        observed_at
        < notice.published_at
    ):
        raise ValueError(
            "observed_at cannot precede published_at."
        )

    source = (
        get_authoritative_event_source(
            notice.source_id
        )
    )

    if (
        classified.market_scope_policy
        == "SOURCE_DEFAULT"
    ):
        markets = (
            source.default_markets
        )

    elif (
        classified.market_scope_policy
        == "SYMBOL_RESOLUTION_REQUIRED"
    ):
        if not resolved_markets:
            return None

        markets = tuple(
            get_target_market(
                market
            ).symbol
            for market
            in resolved_markets
        )

        if any(
            market
            not in {
                "NIFTY",
                "SENSEX",
            }
            for market
            in markets
        ):
            raise ValueError(
                "Company disclosure resolved to unsupported market."
            )

    else:
        raise RuntimeError(
            "Unknown market scope policy."
        )

    if not markets:
        return None

    if len(
        set(
            markets
        )
    ) != len(
        markets
    ):
        raise ValueError(
            "Duplicate resolved markets."
        )

    source_key = (
        notice.source_item_id
        or ""
    )

    published_key = (
        notice.published_at
        .isoformat()
    )

    symbol_key = ",".join(
        notice.affected_symbols
    )

    event_id = _stable_id(
        "INDIA-PRIMARY",
        notice.source_id,
        source_key,
        classified.event_type,
        notice.title,
        published_key,
        symbol_key,
    )

    group_id = _stable_id(
        "INDIA-PRIMARY-GROUP",
        notice.source_id,
        classified.event_type,
        source_key,
        published_key,
        symbol_key,
    )

    return (
        AuthoritativeMarketEventV2(
            event_id=event_id,
            event_group_id=(
                group_id
            ),
            source_id=(
                notice.source_id
            ),
            source_event_id=(
                notice.source_item_id
            ),
            title=(
                notice.title
            ),
            event_type=(
                classified.event_type
            ),
            severity=(
                classified.severity
            ),
            jurisdiction=(
                source.jurisdiction
            ),
            affected_markets=(
                markets
            ),
            affected_symbols=(
                notice.affected_symbols
            ),
            observed_at=(
                observed_at
            ),
            scheduled=False,
            scheduled_at=None,
            published_at=(
                notice.published_at
            ),
            effective_at=None,
            source_url=(
                notice.source_url
            ),
        )
    )
