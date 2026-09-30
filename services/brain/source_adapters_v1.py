"""Pure source adapters for Brain Evidence V1.

These adapters translate values that existing production engines have already
calculated. They deliberately perform no provider I/O, broker I/O, execution,
risk, position-management, certification, or policy-selection work.

B2 invariant:
    adaptation is observation, never authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from services.brain.analyzer_registry_v1 import (
    DEFAULT_ANALYZER_REGISTRY_V1,
)
from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
    EvidenceScalar,
    EvidenceV1,
)


INDEX_MARKETS = frozenset(
    {
        "NIFTY",
        "SENSEX",
    }
)

MCX_MARKETS = frozenset(
    {
        "CRUDEOILM",
        "GOLDM",
        "NATGASMINI",
    }
)


def _require_market(
    market: str,
    allowed: frozenset[str],
) -> None:
    if market not in allowed:
        raise ValueError(
            f"unsupported adapter market: {market}"
        )


def _descriptor(
    analyzer_id: str,
    market: str,
):
    descriptor = DEFAULT_ANALYZER_REGISTRY_V1.get(
        analyzer_id
    )

    if market not in descriptor.markets:
        raise ValueError(
            f"{analyzer_id} does not support {market}"
        )

    if (
        descriptor.execution_authority
        or descriptor.risk_authority
        or descriptor.position_authority
        or descriptor.certification_authority
    ):
        raise ValueError(
            "adapter descriptor unexpectedly has authority"
        )

    return descriptor


def _evidence(
    *,
    analyzer_id: str,
    market: str,
    observed_at: datetime,
    generated_at: datetime,
    category: str,
    feature: str,
    status: str,
    freshness: str,
    source: str,
    value: EvidenceScalar = None,
    unit: str | None = None,
    direction: str = "UNKNOWN",
    strength: float | None = None,
    confidence: float | None = None,
    quality_score: float | None = None,
    source_authoritative: bool = False,
    missing_reason: str | None = None,
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    metadata: tuple[
        tuple[
            str,
            EvidenceScalar,
        ],
        ...,
    ] = (),
) -> EvidenceV1:
    descriptor = _descriptor(
        analyzer_id,
        market,
    )

    return EvidenceV1(
        evidence_id=(
            f"{market}:"
            f"{analyzer_id}:"
            f"{feature}:"
            f"{observed_at.isoformat()}"
        ),
        market=market,
        analyzer=analyzer_id,
        analyzer_version=descriptor.analyzer_version,
        category=category,
        feature=feature,
        observed_at=observed_at,
        generated_at=generated_at,
        status=status,
        freshness=freshness,
        source=source,
        value=value,
        unit=unit,
        direction=direction,
        strength=strength,
        confidence=confidence,
        quality_score=quality_score,
        source_authoritative=source_authoritative,
        missing_reason=missing_reason,
        blockers=blockers,
        warnings=warnings,
        metadata=metadata,
    )


def _result_status(
    evidence: tuple[
        EvidenceV1,
        ...,
    ],
) -> str:
    statuses = {
        item.status
        for item in evidence
    }

    if statuses == {
        "UNAVAILABLE"
    }:
        return "UNAVAILABLE"

    if statuses.intersection(
        {
            "DEGRADED",
            "UNAVAILABLE",
            "UNVERIFIED",
        }
    ):
        return "PARTIAL"

    return "OK"


def _result(
    *,
    analyzer_id: str,
    market: str,
    generated_at: datetime,
    evidence: Iterable[
        EvidenceV1
    ],
    blockers: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> AnalyzerResultV1:
    descriptor = _descriptor(
        analyzer_id,
        market,
    )

    items = tuple(
        evidence
    )

    return AnalyzerResultV1(
        result_id=(
            f"{market}:"
            f"{analyzer_id}:"
            f"{generated_at.isoformat()}"
        ),
        market=market,
        analyzer=analyzer_id,
        analyzer_version=descriptor.analyzer_version,
        generated_at=generated_at,
        status=_result_status(
            items
        ),
        evidence=items,
        blockers=blockers,
        warnings=warnings,
        execution_authority=False,
    )


@dataclass(
    frozen=True,
    slots=True,
)
class IndexPremarketSourceV1:
    """Already-produced index premarket values.

    No field in this source type is recomputed by the adapter.
    """

    market: str
    observed_at: datetime
    generated_at: datetime

    previous_status: str = "AVAILABLE"
    previous_freshness: str = "FRESH"
    previous_source: str = "LEGACY_PREVIOUS_DAY_ENGINE"
    previous_source_authoritative: bool = True
    previous_session_date: str | None = None
    previous_open: float | None = None
    previous_high: float | None = None
    previous_low: float | None = None
    previous_close: float | None = None
    previous_missing_reason: str | None = None

    gap_status: str = "AVAILABLE"
    gap_freshness: str = "FRESH"
    gap_source: str = "LEGACY_GAP_CONTEXT"
    gap_points: float | None = None
    gap_pct: float | None = None
    gap_direction: str = "UNKNOWN"
    gap_missing_reason: str | None = None

    global_status: str = "AVAILABLE"
    global_freshness: str = "UNKNOWN"
    global_source: str = "LEGACY_GLOBAL_MARKETS"
    global_bias: str = "UNKNOWN"
    global_score: float | None = None
    global_source_authoritative: bool = False
    global_missing_reason: str | None = None

    vix_status: str = "AVAILABLE"
    vix_freshness: str = "FRESH"
    vix_source: str = "LEGACY_VIX_ENGINE"
    vix_value: float | None = None
    vix_regime: str | None = None
    vix_direction: str = "UNKNOWN"
    vix_source_authoritative: bool = True
    vix_missing_reason: str | None = None

    flow_status: str = "AVAILABLE"
    flow_freshness: str = "FRESH"
    flow_source: str = "LEGACY_FII_DII_ENGINE"
    fii_cash_net: float | None = None
    dii_cash_net: float | None = None
    combined_net: float | None = None
    flow_direction: str = "UNKNOWN"
    flow_source_authoritative: bool = True
    flow_missing_reason: str | None = None

    event_status: str = "UNVERIFIED"
    event_freshness: str = "UNKNOWN"
    event_source: str = "LEGACY_ECONOMIC_CALENDAR"
    event_direction: str = "UNKNOWN"
    event_source_authoritative: bool = False
    event_provider_block_entries: bool = False
    event_hard_block_eligible: bool = False
    event_threshold_minutes: int | None = None
    event_missing_reason: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class IndexNewsSourceV1:
    market: str
    observed_at: datetime
    generated_at: datetime

    status: str
    freshness: str
    source: str

    sentiment: str
    direction: str

    bullish_count: int
    bearish_count: int
    headline_count: int

    feeds_available: int
    feeds_expected: int

    source_authoritative: bool = False
    missing_reason: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class IndexTechnicalSourceV1:
    """Legacy index technical values exactly as emitted upstream."""

    market: str
    observed_at: datetime
    generated_at: datetime

    status: str = "AVAILABLE"
    freshness: str = "FRESH"
    source: str = "LEGACY_INDEX_MTF"

    mtf_direction: str = "UNKNOWN"

    rsi: float | None = None
    rsi_direction: str = "UNKNOWN"

    adx: float | None = None
    adx_direction: str = "UNKNOWN"

    ema_state: str | None = None
    ema_direction: str = "UNKNOWN"

    macd_state: str | None = None
    macd_direction: str = "UNKNOWN"

    bollinger_state: str | None = None
    bollinger_direction: str = "UNKNOWN"

    regime_status: str = "AVAILABLE"
    regime: str | None = None
    regime_direction: str = "UNKNOWN"

    source_authoritative: bool = True
    missing_reason: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class McxNativeSourceV1:
    """Already-produced MCX native analysis values."""

    market: str
    observed_at: datetime
    generated_at: datetime

    source: str = "MCX_NATIVE_RUNTIME"
    freshness: str = "FRESH"
    source_authoritative: bool = True

    mtf_status: str = "AVAILABLE"
    mtf_direction: str = "UNKNOWN"
    mtf_missing_reason: str | None = None

    regime_status: str = "AVAILABLE"
    regime: str | None = None
    regime_direction: str = "UNKNOWN"
    regime_missing_reason: str | None = None

    structure_status: str = "AVAILABLE"
    structure: str | None = None
    structure_direction: str = "UNKNOWN"
    vwap_relation: str | None = None
    structure_missing_reason: str | None = None

    price_oi_status: str = "AVAILABLE"
    future_ltp: float | None = None
    price_change_pct: float | None = None
    oi_change_pct: float | None = None
    price_oi_state: str | None = None
    price_oi_direction: str = "UNKNOWN"
    price_oi_missing_reason: str | None = None

    pcr_status: str = "AVAILABLE"
    raw_pcr: float | None = None
    stable_pcr: float | None = None
    max_pain: float | None = None
    pcr_direction: str = "UNKNOWN"
    pcr_interpretation: str | None = None
    pcr_missing_reason: str | None = None


def adapt_index_premarket_v1(
    source: IndexPremarketSourceV1,
) -> tuple[
    AnalyzerResultV1,
    ...,
]:
    _require_market(
        source.market,
        INDEX_MARKETS,
    )

    market = source.market
    observed = source.observed_at
    generated = source.generated_at

    previous_id = "index.previous_session.legacy_v1"

    previous = (
        _evidence(
            analyzer_id=previous_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="PREMARKET",
            feature="PREVIOUS_SESSION_CLOSE",
            status=source.previous_status,
            freshness=source.previous_freshness,
            source=source.previous_source,
            value=source.previous_close,
            unit="POINTS",
            source_authoritative=source.previous_source_authoritative,
            missing_reason=source.previous_missing_reason,
            metadata=(
                (
                    "session_date",
                    source.previous_session_date,
                ),
                (
                    "open",
                    source.previous_open,
                ),
                (
                    "high",
                    source.previous_high,
                ),
                (
                    "low",
                    source.previous_low,
                ),
            ),
        ),
    )

    gap_id = "index.gap.legacy_v1"

    gap = (
        _evidence(
            analyzer_id=gap_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="PREMARKET",
            feature="GAP_PCT",
            status=source.gap_status,
            freshness=source.gap_freshness,
            source=source.gap_source,
            value=source.gap_pct,
            unit="PERCENT",
            direction=source.gap_direction,
            source_authoritative=False,
            missing_reason=source.gap_missing_reason,
            metadata=(
                (
                    "gap_points",
                    source.gap_points,
                ),
            ),
        ),
    )

    global_id = "index.global_risk.legacy_v1"

    global_evidence = (
        _evidence(
            analyzer_id=global_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="EXTERNAL",
            feature="GLOBAL_RISK_SCORE",
            status=source.global_status,
            freshness=source.global_freshness,
            source=source.global_source,
            value=source.global_score,
            direction=source.global_bias,
            source_authoritative=source.global_source_authoritative,
            missing_reason=source.global_missing_reason,
        ),
    )

    vix_id = "index.india_vix.legacy_v1"

    vix = (
        _evidence(
            analyzer_id=vix_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="VOLATILITY",
            feature="INDIA_VIX",
            status=source.vix_status,
            freshness=source.vix_freshness,
            source=source.vix_source,
            value=source.vix_value,
            unit="INDEX",
            direction=source.vix_direction,
            source_authoritative=source.vix_source_authoritative,
            missing_reason=source.vix_missing_reason,
            metadata=(
                (
                    "regime",
                    source.vix_regime,
                ),
            ),
        ),
    )

    flow_id = "index.institutional_flow.legacy_v1"

    flow = (
        _evidence(
            analyzer_id=flow_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="FLOW",
            feature="COMBINED_CASH_NET",
            status=source.flow_status,
            freshness=source.flow_freshness,
            source=source.flow_source,
            value=source.combined_net,
            unit="INR_CRORE",
            direction=source.flow_direction,
            source_authoritative=source.flow_source_authoritative,
            missing_reason=source.flow_missing_reason,
            metadata=(
                (
                    "fii_cash_net",
                    source.fii_cash_net,
                ),
                (
                    "dii_cash_net",
                    source.dii_cash_net,
                ),
            ),
        ),
    )

    event_id = "index.event_calendar.legacy_v1"

    event = (
        _evidence(
            analyzer_id=event_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="EVENT",
            feature="EVENT_RISK_STATE",
            status=source.event_status,
            freshness=source.event_freshness,
            source=source.event_source,
            value=None,
            direction=source.event_direction,
            source_authoritative=source.event_source_authoritative,
            missing_reason=source.event_missing_reason,
            metadata=(
                (
                    "provider_block_entries",
                    source.event_provider_block_entries,
                ),
                (
                    "hard_block_eligible",
                    source.event_hard_block_eligible,
                ),
                (
                    "threshold_minutes",
                    source.event_threshold_minutes,
                ),
            ),
        ),
    )

    return (
        _result(
            analyzer_id=previous_id,
            market=market,
            generated_at=generated,
            evidence=previous,
        ),
        _result(
            analyzer_id=gap_id,
            market=market,
            generated_at=generated,
            evidence=gap,
        ),
        _result(
            analyzer_id=global_id,
            market=market,
            generated_at=generated,
            evidence=global_evidence,
        ),
        _result(
            analyzer_id=vix_id,
            market=market,
            generated_at=generated,
            evidence=vix,
        ),
        _result(
            analyzer_id=flow_id,
            market=market,
            generated_at=generated,
            evidence=flow,
        ),
        _result(
            analyzer_id=event_id,
            market=market,
            generated_at=generated,
            evidence=event,
        ),
    )


def adapt_index_news_v1(
    source: IndexNewsSourceV1,
) -> AnalyzerResultV1:
    _require_market(
        source.market,
        INDEX_MARKETS,
    )

    analyzer_id = "index.news.legacy_v1"

    evidence = (
        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="NEWS",
            feature="NEWS_SENTIMENT",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.sentiment,
            direction=source.direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
            metadata=(
                (
                    "bullish_count",
                    source.bullish_count,
                ),
                (
                    "bearish_count",
                    source.bearish_count,
                ),
                (
                    "headline_count",
                    source.headline_count,
                ),
                (
                    "feeds_available",
                    source.feeds_available,
                ),
                (
                    "feeds_expected",
                    source.feeds_expected,
                ),
            ),
        ),
    )

    return _result(
        analyzer_id=analyzer_id,
        market=source.market,
        generated_at=source.generated_at,
        evidence=evidence,
    )


def adapt_index_technical_v1(
    source: IndexTechnicalSourceV1,
) -> tuple[
    AnalyzerResultV1,
    AnalyzerResultV1,
]:
    _require_market(
        source.market,
        INDEX_MARKETS,
    )

    analyzer_id = "index.mtf.legacy_v1"

    evidence = [
        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="TECHNICAL",
            feature="MTF_DIRECTION",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.mtf_direction,
            direction=source.mtf_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
        ),
        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="TECHNICAL",
            feature="RSI",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.rsi,
            unit="INDEX",
            direction=source.rsi_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
        ),
        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="TECHNICAL",
            feature="ADX",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.adx,
            unit="INDEX",
            direction=source.adx_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
        ),
    ]

    optional = (
        (
            "EMA_STATE",
            source.ema_state,
            source.ema_direction,
        ),
        (
            "MACD_STATE",
            source.macd_state,
            source.macd_direction,
        ),
        (
            "BOLLINGER_STATE",
            source.bollinger_state,
            source.bollinger_direction,
        ),
    )

    for feature, value, direction in optional:
        if value is None:
            continue

        evidence.append(
            _evidence(
                analyzer_id=analyzer_id,
                market=source.market,
                observed_at=source.observed_at,
                generated_at=source.generated_at,
                category="TECHNICAL",
                feature=feature,
                status=source.status,
                freshness=source.freshness,
                source=source.source,
                value=value,
                direction=direction,
                source_authoritative=source.source_authoritative,
                missing_reason=source.missing_reason,
            )
        )

    regime_id = "index.regime.legacy_v1"

    regime = (
        _evidence(
            analyzer_id=regime_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="REGIME",
            feature="MARKET_REGIME",
            status=source.regime_status,
            freshness=source.freshness,
            source=source.source,
            value=source.regime,
            direction=source.regime_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=(
                source.missing_reason
                if source.regime_status
                == "UNAVAILABLE"
                else None
            ),
        ),
    )

    return (
        _result(
            analyzer_id=analyzer_id,
            market=source.market,
            generated_at=source.generated_at,
            evidence=evidence,
        ),
        _result(
            analyzer_id=regime_id,
            market=source.market,
            generated_at=source.generated_at,
            evidence=regime,
        ),
    )


def adapt_mcx_native_v1(
    source: McxNativeSourceV1,
) -> tuple[
    AnalyzerResultV1,
    ...,
]:
    _require_market(
        source.market,
        MCX_MARKETS,
    )

    market = source.market
    observed = source.observed_at
    generated = source.generated_at

    mtf_id = "mcx.mtf.native_v1"

    mtf = (
        _evidence(
            analyzer_id=mtf_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="TECHNICAL",
            feature="MTF_DIRECTION",
            status=source.mtf_status,
            freshness=source.freshness,
            source=source.source,
            value=source.mtf_direction,
            direction=source.mtf_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.mtf_missing_reason,
        ),
    )

    regime_id = "mcx.regime.native_v1"

    regime = (
        _evidence(
            analyzer_id=regime_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="REGIME",
            feature="MARKET_REGIME",
            status=source.regime_status,
            freshness=source.freshness,
            source=source.source,
            value=source.regime,
            direction=source.regime_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.regime_missing_reason,
        ),
    )

    structure_id = "mcx.structure.native_v1"

    structure = (
        _evidence(
            analyzer_id=structure_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="STRUCTURE",
            feature="MARKET_STRUCTURE",
            status=source.structure_status,
            freshness=source.freshness,
            source=source.source,
            value=source.structure,
            direction=source.structure_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.structure_missing_reason,
            metadata=(
                (
                    "vwap_relation",
                    source.vwap_relation,
                ),
            ),
        ),
    )

    price_oi_id = "mcx.price_oi.native_v1"

    price_oi = (
        _evidence(
            analyzer_id=price_oi_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="POSITIONING",
            feature="PRICE_OI_STATE",
            status=source.price_oi_status,
            freshness=source.freshness,
            source=source.source,
            value=source.price_oi_state,
            direction=source.price_oi_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.price_oi_missing_reason,
            metadata=(
                (
                    "future_ltp",
                    source.future_ltp,
                ),
                (
                    "price_change_pct",
                    source.price_change_pct,
                ),
                (
                    "oi_change_pct",
                    source.oi_change_pct,
                ),
            ),
        ),
    )

    pcr_id = "mcx.pcr.native_v1"

    pcr = (
        _evidence(
            analyzer_id=pcr_id,
            market=market,
            observed_at=observed,
            generated_at=generated,
            category="OPTIONS",
            feature="STABLE_PCR",
            status=source.pcr_status,
            freshness=source.freshness,
            source=source.source,
            value=source.stable_pcr,
            unit="RATIO",
            direction=source.pcr_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.pcr_missing_reason,
            metadata=(
                (
                    "raw_pcr",
                    source.raw_pcr,
                ),
                (
                    "max_pain",
                    source.max_pain,
                ),
                (
                    "source_interpretation",
                    source.pcr_interpretation,
                ),
            ),
        ),
    )

    return (
        _result(
            analyzer_id=mtf_id,
            market=market,
            generated_at=generated,
            evidence=mtf,
        ),
        _result(
            analyzer_id=regime_id,
            market=market,
            generated_at=generated,
            evidence=regime,
        ),
        _result(
            analyzer_id=structure_id,
            market=market,
            generated_at=generated,
            evidence=structure,
        ),
        _result(
            analyzer_id=price_oi_id,
            market=market,
            generated_at=generated,
            evidence=price_oi,
        ),
        _result(
            analyzer_id=pcr_id,
            market=market,
            generated_at=generated,
            evidence=pcr,
        ),
    )


@dataclass(
    frozen=True,
    slots=True,
)
class IndexBreadthSourceV1:
    """Already-produced index breadth/constituent evidence."""

    market: str
    observed_at: datetime
    generated_at: datetime

    status: str = "AVAILABLE"
    freshness: str = "FRESH"
    source: str = "LEGACY_INDEX_BREADTH"

    breadth_score: float | None = None
    breadth_direction: str = "UNKNOWN"

    advances: int | None = None
    declines: int | None = None
    unchanged: int | None = None

    heavyweight_direction: str | None = None

    source_authoritative: bool = True
    missing_reason: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class IndexOptionChainSourceV1:
    """Already-produced index option-chain evidence.

    PCR direction is supplied by the existing source and is not normalized by
    this adapter.
    """

    market: str
    observed_at: datetime
    generated_at: datetime

    status: str = "AVAILABLE"
    freshness: str = "FRESH"
    source: str = "LEGACY_INDEX_OPTION_CHAIN"

    pcr_value: float | None = None
    pcr_direction: str = "UNKNOWN"
    pcr_interpretation: str | None = None

    max_pain: float | None = None

    support: float | None = None
    resistance: float | None = None

    atm_strike: float | None = None
    expiry: str | None = None

    chain_coverage_pct: float | None = None

    source_authoritative: bool = True
    missing_reason: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class McxEventRiskSourceV1:
    """Already-produced MCX event-risk state."""

    market: str
    observed_at: datetime
    generated_at: datetime

    status: str = "UNVERIFIED"
    freshness: str = "UNKNOWN"
    source: str = "MCX_NATIVE_EVENT_RISK"

    event_state: str | None = None
    event_direction: str = "UNKNOWN"

    event_name: str | None = None
    minutes_to_event: int | None = None

    provider_block_entries: bool = False
    hard_block_eligible: bool = False

    source_authoritative: bool = False
    missing_reason: str | None = None


def adapt_index_breadth_v1(
    source: IndexBreadthSourceV1,
) -> AnalyzerResultV1:
    _require_market(
        source.market,
        INDEX_MARKETS,
    )

    analyzer_id = "index.breadth.legacy_v1"

    evidence = (
        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="BREADTH",
            feature="INDEX_BREADTH",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.breadth_score,
            direction=source.breadth_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
            metadata=(
                (
                    "advances",
                    source.advances,
                ),
                (
                    "declines",
                    source.declines,
                ),
                (
                    "unchanged",
                    source.unchanged,
                ),
                (
                    "heavyweight_direction",
                    source.heavyweight_direction,
                ),
            ),
        ),
    )

    return _result(
        analyzer_id=analyzer_id,
        market=source.market,
        generated_at=source.generated_at,
        evidence=evidence,
    )


def adapt_index_option_chain_v1(
    source: IndexOptionChainSourceV1,
) -> AnalyzerResultV1:
    _require_market(
        source.market,
        INDEX_MARKETS,
    )

    analyzer_id = "index.option_chain.legacy_v1"

    evidence = [
        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="OPTIONS",
            feature="PCR",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.pcr_value,
            unit="RATIO",
            direction=source.pcr_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
            metadata=(
                (
                    "source_interpretation",
                    source.pcr_interpretation,
                ),
                (
                    "atm_strike",
                    source.atm_strike,
                ),
                (
                    "expiry",
                    source.expiry,
                ),
                (
                    "chain_coverage_pct",
                    source.chain_coverage_pct,
                ),
            ),
        ),

        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="OPTIONS",
            feature="MAX_PAIN",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.max_pain,
            unit="STRIKE",
            direction="UNKNOWN",
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
        ),
    ]


    if source.support is not None:

        evidence.append(
            _evidence(
                analyzer_id=analyzer_id,
                market=source.market,
                observed_at=source.observed_at,
                generated_at=source.generated_at,
                category="OPTIONS",
                feature="SUPPORT",
                status=source.status,
                freshness=source.freshness,
                source=source.source,
                value=source.support,
                unit="STRIKE",
                direction="BULLISH",
                source_authoritative=source.source_authoritative,
                missing_reason=source.missing_reason,
            )
        )


    if source.resistance is not None:

        evidence.append(
            _evidence(
                analyzer_id=analyzer_id,
                market=source.market,
                observed_at=source.observed_at,
                generated_at=source.generated_at,
                category="OPTIONS",
                feature="RESISTANCE",
                status=source.status,
                freshness=source.freshness,
                source=source.source,
                value=source.resistance,
                unit="STRIKE",
                direction="BEARISH",
                source_authoritative=source.source_authoritative,
                missing_reason=source.missing_reason,
            )
        )


    return _result(
        analyzer_id=analyzer_id,
        market=source.market,
        generated_at=source.generated_at,
        evidence=evidence,
    )


def adapt_mcx_event_risk_v1(
    source: McxEventRiskSourceV1,
) -> AnalyzerResultV1:
    _require_market(
        source.market,
        MCX_MARKETS,
    )

    analyzer_id = "mcx.event_risk.native_v1"

    evidence = (
        _evidence(
            analyzer_id=analyzer_id,
            market=source.market,
            observed_at=source.observed_at,
            generated_at=source.generated_at,
            category="EVENT",
            feature="EVENT_RISK_STATE",
            status=source.status,
            freshness=source.freshness,
            source=source.source,
            value=source.event_state,
            direction=source.event_direction,
            source_authoritative=source.source_authoritative,
            missing_reason=source.missing_reason,
            metadata=(
                (
                    "event_name",
                    source.event_name,
                ),
                (
                    "minutes_to_event",
                    source.minutes_to_event,
                ),
                (
                    "provider_block_entries",
                    source.provider_block_entries,
                ),
                (
                    "hard_block_eligible",
                    source.hard_block_eligible,
                ),
            ),
        ),
    )

    return _result(
        analyzer_id=analyzer_id,
        market=source.market,
        generated_at=source.generated_at,
        evidence=evidence,
    )


__all__ = [
    "IndexBreadthSourceV1",
    "IndexNewsSourceV1",
    "IndexOptionChainSourceV1",
    "IndexPremarketSourceV1",
    "IndexTechnicalSourceV1",
    "McxEventRiskSourceV1",
    "McxNativeSourceV1",
    "adapt_index_breadth_v1",
    "adapt_index_news_v1",
    "adapt_index_option_chain_v1",
    "adapt_index_premarket_v1",
    "adapt_index_technical_v1",
    "adapt_mcx_event_risk_v1",
    "adapt_mcx_native_v1",
]
