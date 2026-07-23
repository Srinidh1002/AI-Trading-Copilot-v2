"""Multi-timeframe alignment analysis over pre-calculated technical snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MultiTimeframeConfig:
    """Timeframe ordering and confirmation thresholds for alignment analysis."""

    neutral_score_band: float = 5.0
    bullish_rsi: float = 55.0
    bearish_rsi: float = 45.0
    strong_adx: float = 25.0
    timeframe_order: tuple[str, ...] = ("1m", "3m", "5m", "15m", "30m", "1h", "1d")
    entry_candidates: tuple[str, ...] = ("5m", "3m", "1m", "15m", "30m", "1h", "1d")
    trade_candidates: tuple[str, ...] = ("15m", "30m", "5m", "1h", "3m", "1m", "1d")
    exit_candidates: tuple[str, ...] = ("1h", "30m", "15m", "1d", "5m", "3m", "1m")


@dataclass(slots=True)
class TimeframeAssessment:
    timeframe: str
    direction: str
    trend_strength: float
    momentum_strength: float
    confidence: float
    ema_aligned: bool
    macd_aligned: bool
    rsi_aligned: bool
    adx_confirmed: bool
    vwap_aligned: bool


class MultiTimeframeEngine:
    """Determine directional confluence without fetching data or computing indicators."""

    def __init__(self, config: MultiTimeframeConfig | None = None) -> None:
        self.config = config or MultiTimeframeConfig()

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _number(data: Mapping[str, Any], *keys: str) -> float | None:
        for key in keys:
            try:
                value = float(data.get(key))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                return value
        return None

    @staticmethod
    def _clamp(value: float) -> float:
        return round(min(100.0, max(0.0, value)), 2)

    @staticmethod
    def _normalise_direction(value: Any) -> str | None:
        text = str(value or "").strip().upper()
        if text in {"BULLISH", "BULL", "BUY", "UP", "UPTREND", "LONG"}:
            return "BULLISH"
        if text in {"BEARISH", "BEAR", "SELL", "DOWN", "DOWNTREND", "SHORT"}:
            return "BEARISH"
        if text in {"NEUTRAL", "SIDEWAYS", "RANGE", "HOLD", "WAIT"}:
            return "NEUTRAL"
        return None

    def _score_direction(self, snapshot: Mapping[str, Any]) -> tuple[str | None, float]:
        bull = self._number(snapshot, "bull_score", "bull")
        bear = self._number(snapshot, "bear_score", "bear")
        if bull is None or bear is None or bull + bear <= 0:
            return None, 0.0
        delta = (bull - bear) * 100.0 / (bull + bear)
        if abs(delta) <= self.config.neutral_score_band:
            return "NEUTRAL", abs(delta)
        return ("BULLISH" if delta > 0 else "BEARISH"), abs(delta)

    def _assess(self, timeframe: str, source: Mapping[str, Any]) -> TimeframeAssessment | None:
        snapshot = self._mapping(source.get("indicators")) or source
        if not snapshot:
            return None
        declared_direction = self._normalise_direction(source.get("trend", snapshot.get("trend")))
        scored_direction, score_strength = self._score_direction(source)
        price, ema20, ema50, ema200 = (self._number(snapshot, key) for key in ("CURRENT_PRICE", "EMA20", "EMA50", "EMA200"))
        rsi, macd, macd_signal, adx, vwap = (self._number(snapshot, key) for key in ("RSI", "MACD", "MACD_SIGNAL", "ADX", "VWAP"))
        ema_bull = None not in (price, ema20, ema50, ema200) and price > ema20 > ema50 > ema200
        ema_bear = None not in (price, ema20, ema50, ema200) and price < ema20 < ema50 < ema200
        ema_direction = "BULLISH" if ema_bull else "BEARISH" if ema_bear else None
        direction = declared_direction or scored_direction or ema_direction or "NEUTRAL"
        macd_direction = "BULLISH" if macd is not None and macd_signal is not None and macd > macd_signal else "BEARISH" if macd is not None and macd_signal is not None and macd < macd_signal else None
        rsi_direction = "BULLISH" if rsi is not None and rsi >= self.config.bullish_rsi else "BEARISH" if rsi is not None and rsi <= self.config.bearish_rsi else None
        vwap_direction = "BULLISH" if price is not None and vwap is not None and price > vwap else "BEARISH" if price is not None and vwap is not None and price < vwap else None
        ema_aligned = ema_direction == direction
        macd_aligned = macd_direction == direction
        rsi_aligned = rsi_direction == direction
        vwap_aligned = vwap_direction == direction
        adx_confirmed = adx is not None and adx >= self.config.strong_adx
        trend_strength = score_strength * 0.35 + (25.0 if ema_aligned else 0.0) + (20.0 if adx_confirmed else 0.0) + (10.0 if vwap_aligned else 0.0)
        momentum_strength = (40.0 if macd_aligned else 0.0) + (35.0 if rsi_aligned else 0.0) + (25.0 if vwap_aligned else 0.0)
        confidence = self._number(source, "confidence")
        if confidence is None:
            confidence = self._number(snapshot, "confidence")
        return TimeframeAssessment(timeframe=timeframe, direction=direction, trend_strength=self._clamp(trend_strength), momentum_strength=self._clamp(momentum_strength), confidence=self._clamp(confidence or 0.0), ema_aligned=ema_aligned, macd_aligned=macd_aligned, rsi_aligned=rsi_aligned, adx_confirmed=adx_confirmed, vwap_aligned=vwap_aligned)

    def analyze(self, timeframes: Mapping[str, Any] | None) -> dict[str, Any]:
        """Analyze supplied timeframe snapshots and return directional confluence."""
        try:
            if not isinstance(timeframes, Mapping) or not timeframes:
                return self._empty_result("No timeframe snapshots were supplied.")
            assessments: list[TimeframeAssessment] = []
            known = list(self.config.timeframe_order)
            ordered = [name for name in known if name in timeframes] + sorted(name for name in timeframes if name not in known)
            for timeframe in ordered:
                value = timeframes.get(timeframe)
                if not isinstance(value, Mapping):
                    logger.warning("Ignoring malformed %s timeframe snapshot", timeframe)
                    continue
                assessment = self._assess(timeframe, value)
                if assessment is not None:
                    assessments.append(assessment)
            if not assessments:
                return self._empty_result("No valid timeframe snapshots were supplied.")
            grouped = {direction: [item for item in assessments if item.direction == direction] for direction in ("BULLISH", "BEARISH", "NEUTRAL")}
            dominant = max(("BULLISH", "BEARISH", "NEUTRAL"), key=lambda direction: len(grouped[direction]))
            alignment_percent = self._clamp(len(grouped[dominant]) * 100.0 / len(assessments))
            highest = max(assessments, key=lambda item: item.confidence)
            lowest = min(assessments, key=lambda item: item.confidence)
            strongest = max(assessments, key=lambda item: (item.trend_strength, item.confidence))
            trade = self._select_timeframe(self.config.trade_candidates, assessments, dominant)
            entry = self._select_timeframe(self.config.entry_candidates, assessments, dominant)
            exit_timeframe = self._select_timeframe(self.config.exit_candidates, assessments, dominant)
            reasons = self._reasons(assessments, grouped, dominant, alignment_percent)
            return {"overall_trend": dominant, "alignment_percent": alignment_percent, "bullish_timeframes": [item.timeframe for item in grouped["BULLISH"]], "bearish_timeframes": [item.timeframe for item in grouped["BEARISH"]], "neutral_timeframes": [item.timeframe for item in grouped["NEUTRAL"]], "highest_confidence_timeframe": highest.timeframe, "lowest_confidence_timeframe": lowest.timeframe, "strongest_trend": strongest.timeframe, "trade_timeframe": trade, "entry_timeframe": entry, "exit_timeframe": exit_timeframe, "reasons": reasons}
        except Exception as exc:
            logger.exception("Multi-timeframe analysis failed")
            return self._empty_result(f"Multi-timeframe analysis failed: {type(exc).__name__}.")

    def _select_timeframe(self, candidates: tuple[str, ...], assessments: list[TimeframeAssessment], direction: str) -> str:
        by_name = {item.timeframe: item for item in assessments}
        for candidate in candidates:
            assessment = by_name.get(candidate)
            if assessment is not None and assessment.direction == direction:
                return candidate
        aligned = [item for item in assessments if item.direction == direction]
        return max(aligned, key=lambda item: (item.trend_strength, item.confidence)).timeframe if aligned else ""

    def _reasons(self, assessments: list[TimeframeAssessment], grouped: dict[str, list[TimeframeAssessment]], dominant: str, alignment: float) -> list[str]:
        reasons: list[str] = []
        short = [item for item in assessments if item.timeframe in {"1m", "3m", "5m", "15m"}]
        long = [item for item in assessments if item.timeframe in {"30m", "1h", "1d"}]
        if dominant == "BULLISH" and alignment == 100.0:
            reasons.append("Full Bull Alignment: every supplied timeframe is bullish.")
        elif dominant == "BEARISH" and alignment == 100.0:
            reasons.append("Full Bear Alignment: every supplied timeframe is bearish.")
        elif long and all(item.direction == "BULLISH" for item in long) and any(item.direction == "BEARISH" for item in short):
            reasons.append("Short-term Pullback: bearish lower timeframes oppose the bullish long-term trend.")
        elif long and all(item.direction == "BEARISH" for item in long) and any(item.direction == "BULLISH" for item in short):
            reasons.append("Short-term Pullback: bullish lower timeframes oppose the bearish long-term trend.")
        elif long and len({item.direction for item in long}) == 1 and long[0].direction in {"BULLISH", "BEARISH"}:
            reasons.append(f"Long-term Trend: higher timeframes are {long[0].direction.lower()}.")
        if long and short and {item.direction for item in long if item.direction != "NEUTRAL"} and {item.direction for item in short if item.direction != "NEUTRAL"} and dominant == "NEUTRAL":
            reasons.append("Counter Trend: higher and lower timeframes do not establish a dominant direction.")
        if alignment < 50.0:
            reasons.append("No Alignment: fewer than half of supplied timeframes agree.")
        elif alignment < 75.0:
            reasons.append("Mixed Market: timeframe alignment is partial.")
        transitions = sum(not item.ema_aligned or not item.macd_aligned for item in assessments)
        if transitions >= max(2, len(assessments) // 2):
            reasons.append("Trend Transition: EMA or MACD confirmation is incomplete across multiple timeframes.")
        confirmed_adx = sum(item.adx_confirmed for item in assessments)
        confirmed_vwap = sum(item.vwap_aligned for item in assessments)
        reasons.append(f"Trend alignment is {alignment:.2f}% across {len(assessments)} valid timeframe snapshots.")
        reasons.append(f"ADX confirms {confirmed_adx} and VWAP confirms {confirmed_vwap} timeframes.")
        return reasons

    @staticmethod
    def _empty_result(reason: str) -> dict[str, Any]:
        return {"overall_trend": "NEUTRAL", "alignment_percent": 0.0, "bullish_timeframes": [], "bearish_timeframes": [], "neutral_timeframes": [], "highest_confidence_timeframe": "", "lowest_confidence_timeframe": "", "strongest_trend": "", "trade_timeframe": "", "entry_timeframe": "", "exit_timeframe": "", "reasons": [reason]}


def analyze_multi_timeframe(timeframes: Mapping[str, Any] | None) -> dict[str, Any]:
    """Convenience entry point for snapshot-only timeframe alignment analysis."""
    return MultiTimeframeEngine().analyze(timeframes)
