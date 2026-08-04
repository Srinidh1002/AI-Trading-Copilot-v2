"""Pure adapters between canonical contracts and legacy analysis engines."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd

from services.contracts.analysis_result_v1 import (
    AlignmentStatus,
    DirectionalBias,
    EvidenceSection,
    EvidenceSignal,
    EvidenceStatus,
    MultiTimeframeSummary,
    TimeframeState,
)
from services.contracts.market_snapshot_v1 import MarketSnapshotV1


def canonical_timeframes_to_frames(
    snapshot: MarketSnapshotV1,
) -> dict[str, pd.DataFrame]:
    """Materialize canonical OHLCV values for analysis-only legacy engines."""
    frames: dict[str, pd.DataFrame] = {}
    for timeframe, series in snapshot.timeframes.items():
        frames[timeframe] = pd.DataFrame(
            [bar.to_dict() for bar in series.bars],
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
    return frames


def normalize_bias(value: Any) -> str:
    value = str(value or "").upper()
    if value in {"BULLISH", "BUY", "UPTREND"}:
        return DirectionalBias.BULLISH.value
    if value in {"BEARISH", "SELL", "DOWNTREND"}:
        return DirectionalBias.BEARISH.value
    if value in {"CONFLICTED", "MIXED"}:
        return DirectionalBias.CONFLICTED.value
    if value in {"NEUTRAL", "SIDEWAYS", "HOLD", "RANGE"}:
        return DirectionalBias.NEUTRAL.value
    return DirectionalBias.UNKNOWN.value


def evidence_signal(value: Any) -> str:
    bias = normalize_bias(value)
    if bias == DirectionalBias.BULLISH.value:
        return EvidenceSignal.BULLISH.value
    if bias == DirectionalBias.BEARISH.value:
        return EvidenceSignal.BEARISH.value
    if bias == DirectionalBias.CONFLICTED.value:
        return EvidenceSignal.MIXED.value
    return EvidenceSignal.NEUTRAL.value


def bounded_score(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(min(100.0, max(0.0, number)), 2) if math.isfinite(number) else None


def error_evidence(error: Exception) -> EvidenceSection:
    return EvidenceSection(
        status=EvidenceStatus.ERROR,
        signal=EvidenceSignal.UNAVAILABLE,
        errors=(f"{type(error).__name__}: {error}",),
    )


def unavailable_evidence(reason: str, *, status: str = EvidenceStatus.UNAVAILABLE) -> EvidenceSection:
    return EvidenceSection(
        status=status,
        signal=EvidenceSignal.UNAVAILABLE,
        warnings=(reason,),
    )


def evidence_from_mapping(
    payload: Mapping[str, Any],
    *,
    signal_key: str = "signal",
    score_key: str = "score",
    confidence_key: str = "confidence",
    reasons_key: str = "reasons",
    contradictions: tuple[str, ...] = (),
) -> EvidenceSection:
    reasons = payload.get(reasons_key, ())
    if not isinstance(reasons, (list, tuple)):
        reasons = ()
    return EvidenceSection(
        status=EvidenceStatus.VALID,
        signal=evidence_signal(payload.get(signal_key)),
        score=bounded_score(payload.get(score_key)),
        confidence=bounded_score(payload.get(confidence_key)),
        reasons=tuple(str(item) for item in reasons),
        contradictions=contradictions,
        metadata=dict(payload),
    )


def multi_timeframe_summary(
    payload: Mapping[str, Any],
    available_timeframes: set[str],
) -> MultiTimeframeSummary:
    results = payload.get("timeframe_results", {})
    results = results if isinstance(results, Mapping) else {}
    states: dict[str, TimeframeState] = {}
    for timeframe, result in results.items():
        result = result if isinstance(result, Mapping) else {}
        states[str(timeframe)] = TimeframeState(
            timeframe=str(timeframe),
            direction=normalize_bias(result.get("trend")),
            trend_strength=bounded_score(result.get("confidence")),
            status=EvidenceStatus.VALID,
            reasons=tuple(str(item) for item in result.get("reasons", ())),
        )

    missing = tuple(
        timeframe for timeframe in ("5m", "15m", "1h", "1d")
        if timeframe not in available_timeframes
    )
    alignment_value = str(payload.get("alignment", "")).upper()
    trend = normalize_bias(payload.get("overall_trend"))
    if alignment_value == "FULL" and trend == DirectionalBias.BULLISH.value:
        alignment = AlignmentStatus.ALIGNED_BULLISH.value
    elif alignment_value == "FULL" and trend == DirectionalBias.BEARISH.value:
        alignment = AlignmentStatus.ALIGNED_BEARISH.value
    elif alignment_value == "CONFLICTED":
        alignment = AlignmentStatus.CONFLICTED.value
    elif results:
        alignment = AlignmentStatus.MIXED.value
    else:
        alignment = AlignmentStatus.INSUFFICIENT_DATA.value
    return MultiTimeframeSummary(
        alignment=alignment,
        primary_timeframe="5m" if "5m" in available_timeframes else None,
        confirmation_timeframe="15m" if "15m" in available_timeframes else None,
        higher_timeframe="1h" if "1h" in available_timeframes else None,
        states=states,
        conflicting_timeframes=(
            tuple(results) if alignment == AlignmentStatus.CONFLICTED.value else ()
        ),
        missing_timeframes=missing,
        warnings=tuple(str(item) for item in payload.get("reasons", ())),
    )


def snapshot_data_quality(snapshot: MarketSnapshotV1) -> float:
    if not snapshot.validation_passed:
        return 0.0
    if snapshot.is_stale:
        return 25.0
    return 100.0
