"""Pure builder for canonical previous-session and pre-market intelligence.

This module adapts existing engine payloads into V2 contracts.  It performs no
network requests and makes no trading decision.
"""

from __future__ import annotations

from datetime import date, datetime
import math

from services.contracts.premarket_intelligence_v2 import (
    EventRiskContextV2,
    GapContextV2,
    GlobalRiskContextV2,
    InstitutionalCashFlowV2,
    PreMarketStateV2,
    PreviousSessionIntelligenceV2,
    VolatilityContextV2,
)
from services.core.five_market_universe_v2 import (
    get_target_market,
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


def _float_or_none(
    value: object,
) -> float | None:
    try:
        result = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        result
    ):
        return None

    return result


def _parse_date(
    value: object,
) -> date | None:
    if isinstance(
        value,
        date,
    ):
        return value

    if not isinstance(
        value,
        str,
    ):
        return None

    text = value.strip()

    if not text:
        return None

    try:
        return date.fromisoformat(
            text[:10]
        )
    except ValueError:
        return None


def _previous_session(
    *,
    market_symbol: str,
    payload: dict | None,
    observed_at: datetime,
) -> tuple[
    str,
    PreviousSessionIntelligenceV2 | None,
]:
    data = (
        payload
        if isinstance(
            payload,
            dict,
        )
        else {}
    )

    if data.get(
        "status"
    ) != "OK":
        return (
            "UNAVAILABLE",
            None,
        )

    session_date = _parse_date(
        data.get(
            "date"
        )
    )

    if session_date is None:
        return (
            "UNAVAILABLE",
            None,
        )

    values = {
        key: _float_or_none(
            data.get(
                key
            )
        )
        for key in (
            "open",
            "high",
            "low",
            "close",
            "range",
            "range_pct",
            "body_pct",
            "close_location",
            "atr14",
        )
    }

    required = (
        "open",
        "high",
        "low",
        "close",
        "range",
        "range_pct",
        "body_pct",
        "close_location",
    )

    if any(
        values[key] is None
        for key in required
    ):
        return (
            "UNAVAILABLE",
            None,
        )

    try:
        snapshot = (
            PreviousSessionIntelligenceV2(
                market_symbol=market_symbol,
                session_date=session_date,
                open=values["open"],
                high=values["high"],
                low=values["low"],
                close=values["close"],
                range_points=values["range"],
                range_pct=values["range_pct"],
                body_pct=values["body_pct"],
                direction=str(
                    data.get(
                        "direction",
                        "",
                    )
                ),
                close_location=values[
                    "close_location"
                ],
                day_type=str(
                    data.get(
                        "day_type",
                        "",
                    )
                ),
                atr14=values[
                    "atr14"
                ],
                source=(
                    "LEGACY_PREVIOUS_DAY_ENGINE"
                ),
                observed_at=observed_at,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return (
            "UNAVAILABLE",
            None,
        )

    return (
        "AVAILABLE",
        snapshot,
    )


def _gap_context(
    *,
    previous_session: PreviousSessionIntelligenceV2 | None,
    session_open: float | None,
    observed_at: datetime,
) -> GapContextV2 | None:
    if previous_session is None:
        return None

    session_open_value = _float_or_none(
        session_open
    )

    if (
        session_open_value is None
        or session_open_value <= 0
    ):
        return None

    previous_close = (
        previous_session.close
    )

    gap_points = (
        session_open_value
        - previous_close
    )

    gap_pct = (
        gap_points
        / previous_close
        * 100
    )

    atr_multiple = None

    if (
        previous_session.atr14
        is not None
        and previous_session.atr14 > 0
    ):
        atr_multiple = (
            gap_points
            / previous_session.atr14
        )

    direction = (
        "UP"
        if gap_points > 0
        else (
            "DOWN"
            if gap_points < 0
            else "FLAT"
        )
    )

    return GapContextV2(
        previous_close=previous_close,
        session_open=session_open_value,
        gap_points=gap_points,
        gap_pct=gap_pct,
        atr_multiple=atr_multiple,
        direction=direction,
        observed_at=observed_at,
    )


def _global_risk(
    *,
    payload: dict | None,
    observed_at: datetime,
) -> GlobalRiskContextV2:
    data = (
        payload
        if isinstance(
            payload,
            dict,
        )
        else {}
    )

    risk = (
        data.get(
            "risk"
        )
        if isinstance(
            data.get(
                "risk"
            ),
            dict,
        )
        else {}
    )

    if (
        data.get(
            "status"
        )
        == "OK"
        and risk
    ):
        return GlobalRiskContextV2(
            evidence_status="AVAILABLE",
            sentiment=str(
                risk.get(
                    "sentiment",
                    "UNKNOWN",
                )
            ),
            confidence=(
                _float_or_none(
                    risk.get(
                        "confidence"
                    )
                )
            ),
            coverage=(
                str(
                    data.get(
                        "coverage"
                    )
                )
                if data.get(
                    "coverage"
                )
                is not None
                else None
            ),
            source="LEGACY_EXTERNAL_INTEL",
            observed_at=observed_at,
            freshness_status="UNKNOWN",
        )

    return GlobalRiskContextV2(
        evidence_status="UNAVAILABLE",
        sentiment="UNKNOWN",
        confidence=None,
        coverage=None,
        source="LEGACY_EXTERNAL_INTEL",
        observed_at=observed_at,
        freshness_status="UNKNOWN",
    )


def _volatility(
    *,
    payload: dict | None,
    observed_at: datetime,
) -> VolatilityContextV2:
    data = (
        payload
        if isinstance(
            payload,
            dict,
        )
        else {}
    )

    if data.get(
        "status"
    ) == "OK":
        return VolatilityContextV2(
            evidence_status="AVAILABLE",
            vix=_float_or_none(
                data.get(
                    "vix"
                )
            ),
            change_1d_pct=(
                _float_or_none(
                    data.get(
                        "change_1d_pct"
                    )
                )
            ),
            percentile=(
                _float_or_none(
                    data.get(
                        "percentile_45d"
                    )
                )
            ),
            regime=str(
                data.get(
                    "regime",
                    "UNKNOWN",
                )
            ),
            trend=str(
                data.get(
                    "trend",
                    "UNKNOWN",
                )
            ),
            source="LEGACY_ENHANCED_VIX",
            observed_at=observed_at,
        )

    return VolatilityContextV2(
        evidence_status="UNAVAILABLE",
        vix=None,
        change_1d_pct=None,
        percentile=None,
        regime="UNKNOWN",
        trend="UNKNOWN",
        source="LEGACY_ENHANCED_VIX",
        observed_at=observed_at,
    )


def _institutional_flow(
    *,
    payload: dict | None,
    observed_at: datetime,
) -> InstitutionalCashFlowV2:
    data = (
        payload
        if isinstance(
            payload,
            dict,
        )
        else {}
    )

    if data.get(
        "status"
    ) == "OK":
        return InstitutionalCashFlowV2(
            evidence_status="AVAILABLE",
            trade_date=(
                str(
                    data.get(
                        "trade_date"
                    )
                )
                if data.get(
                    "trade_date"
                )
                is not None
                else None
            ),
            fii_cash_net=(
                _float_or_none(
                    data.get(
                        "fii_cash_net"
                    )
                )
            ),
            dii_cash_net=(
                _float_or_none(
                    data.get(
                        "dii_cash_net"
                    )
                )
            ),
            combined_net=(
                _float_or_none(
                    data.get(
                        "combined_net"
                    )
                )
            ),
            bias=str(
                data.get(
                    "bias",
                    "UNKNOWN",
                )
            ),
            source="LEGACY_FII_DII_ENGINE",
            observed_at=observed_at,
        )

    return InstitutionalCashFlowV2(
        evidence_status="UNAVAILABLE",
        trade_date=None,
        fii_cash_net=None,
        dii_cash_net=None,
        combined_net=None,
        bias="UNKNOWN",
        source="LEGACY_FII_DII_ENGINE",
        observed_at=observed_at,
    )


def _event_risk(
    *,
    payload: dict | None,
    observed_at: datetime,
    source_authoritative: bool,
) -> EventRiskContextV2:
    data = (
        payload
        if isinstance(
            payload,
            dict,
        )
        else {}
    )

    has_payload = bool(
        data
    )

    provider_block = bool(
        data.get(
            "block_entries",
            False,
        )
    )

    events = (
        data.get(
            "events"
        )
        if isinstance(
            data.get(
                "events"
            ),
            list,
        )
        else []
    )

    event_names = tuple(
        str(
            event.get(
                "name"
            )
        ).strip()
        for event in events
        if (
            isinstance(
                event,
                dict,
            )
            and str(
                event.get(
                    "name",
                    "",
                )
            ).strip()
        )
    )

    threshold = data.get(
        "threshold_minutes"
    )

    if not isinstance(
        threshold,
        int,
    ) or isinstance(
        threshold,
        bool,
    ):
        threshold = None

    if not has_payload:
        status = "UNAVAILABLE"

    elif source_authoritative:
        status = "AVAILABLE"

    else:
        status = "UNVERIFIED"

    hard_block_eligible = (
        status == "AVAILABLE"
        and source_authoritative
        and provider_block
    )

    return EventRiskContextV2(
        evidence_status=status,
        source_authoritative=(
            source_authoritative
        ),
        provider_block_entries=(
            provider_block
        ),
        hard_block_eligible=(
            hard_block_eligible
        ),
        event_names=event_names,
        threshold_minutes=threshold,
        source=(
            "AUTHORITATIVE_EVENT_SOURCE"
            if source_authoritative
            else "LEGACY_ECONOMIC_CALENDAR"
        ),
        observed_at=observed_at,
    )


def build_premarket_state_v2(
    *,
    market_symbol: str,
    generated_at: datetime,
    previous_day_payload: dict | None,
    session_open: float | None,
    external_payload: dict | None,
    vix_payload: dict | None,
    fii_dii_payload: dict | None,
    event_payload: dict | None,
    event_source_authoritative: bool = False,
) -> PreMarketStateV2:
    """Normalize existing engine outputs into one canonical pre-market state."""

    market = get_target_market(
        market_symbol
    )

    if not _aware(
        generated_at
    ):
        raise ValueError(
            "generated_at must be timezone-aware."
        )

    (
        previous_status,
        previous_session,
    ) = _previous_session(
        market_symbol=market.symbol,
        payload=previous_day_payload,
        observed_at=generated_at,
    )

    gap = _gap_context(
        previous_session=previous_session,
        session_open=session_open,
        observed_at=generated_at,
    )

    return PreMarketStateV2(
        market_symbol=market.symbol,
        generated_at=generated_at,
        previous_session_status=(
            previous_status
        ),
        previous_session=(
            previous_session
        ),
        gap=gap,
        global_risk=_global_risk(
            payload=external_payload,
            observed_at=generated_at,
        ),
        volatility=_volatility(
            payload=vix_payload,
            observed_at=generated_at,
        ),
        institutional_flow=(
            _institutional_flow(
                payload=fii_dii_payload,
                observed_at=generated_at,
            )
        ),
        event_risk=_event_risk(
            payload=event_payload,
            observed_at=generated_at,
            source_authoritative=(
                event_source_authoritative
            ),
        ),
    )
