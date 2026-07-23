"""Market-context scoring built from an existing technical-indicator snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MarketScoreConfig:
    trend_weight: float = 30.0
    momentum_weight: float = 20.0
    volume_weight: float = 15.0
    price_action_weight: float = 15.0
    volatility_weight: float = 10.0
    context_weight: float = 10.0
    strong_adx: float = 25.0
    high_adx: float = 35.0
    vix_elevated: float = 20.0
    vix_extreme: float = 28.0
    gap_threshold: float = 0.5


@dataclass(slots=True)
class DirectionalScore:
    bull: float = 0.0
    bear: float = 0.0
    reasons: list[str] | None = None

    def __post_init__(self) -> None:
        if self.reasons is None:
            self.reasons = []


class MarketScoreEngine:
    """Score market conditions without recalculating any technical indicator."""

    def __init__(self, config: MarketScoreConfig | None = None) -> None:
        self.config = config or MarketScoreConfig()

    @staticmethod
    def _indicators(technical: Mapping[str, Any] | None) -> Mapping[str, Any]:
        if not isinstance(technical, Mapping):
            return {}
        nested = technical.get("indicators")
        return nested if isinstance(nested, Mapping) else technical

    @staticmethod
    def _number(values: Mapping[str, Any], name: str) -> float | None:
        try:
            value = float(values.get(name))
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None

    @staticmethod
    def _flag(values: Mapping[str, Any], name: str) -> bool:
        value = values.get(name, False)
        return value is True or str(value).strip().upper() in {"TRUE", "YES", "1", "BULLISH"}

    @staticmethod
    def _bounded(score: DirectionalScore, weight: float) -> DirectionalScore:
        score.bull = round(min(weight, max(0.0, score.bull)), 2)
        score.bear = round(min(weight, max(0.0, score.bear)), 2)
        return score

    def score_trend(self, technical: Mapping[str, Any] | None) -> DirectionalScore:
        data, weight = self._indicators(technical), self.config.trend_weight
        ema20, ema50, ema200 = (self._number(data, key) for key in ("EMA20", "EMA50", "EMA200"))
        price = self._number(data, "CURRENT_PRICE")
        adx = self._number(data, "ADX")
        result = DirectionalScore()
        if None not in (ema20, ema50, ema200):
            if ema20 > ema50 > ema200:
                result.bull += weight * 0.7; result.reasons.append("EMA alignment is bullish")
            elif ema20 < ema50 < ema200:
                result.bear += weight * 0.7; result.reasons.append("EMA alignment is bearish")
        if price is not None and ema20 is not None:
            if price > ema20: result.bull += weight * 0.15
            elif price < ema20: result.bear += weight * 0.15
        if adx is not None and adx >= self.config.strong_adx:
            boost = weight * (0.15 if adx >= self.config.high_adx else 0.08)
            if result.bull > result.bear: result.bull += boost; result.reasons.append("ADX confirms bullish trend strength")
            elif result.bear > result.bull: result.bear += boost; result.reasons.append("ADX confirms bearish trend strength")
        return self._bounded(result, weight)

    def score_momentum(self, technical: Mapping[str, Any] | None) -> DirectionalScore:
        data, weight, result = self._indicators(technical), self.config.momentum_weight, DirectionalScore()
        rsi, macd, signal, histogram = (self._number(data, key) for key in ("RSI", "MACD", "MACD_SIGNAL", "MACD_HISTOGRAM"))
        if rsi is not None:
            if rsi >= 60: result.bull += weight * 0.35; result.reasons.append("RSI shows positive momentum")
            elif rsi <= 40: result.bear += weight * 0.35; result.reasons.append("RSI shows negative momentum")
        if macd is not None and signal is not None:
            if macd > signal: result.bull += weight * 0.4; result.reasons.append("MACD is above its signal line")
            elif macd < signal: result.bear += weight * 0.4; result.reasons.append("MACD is below its signal line")
        if histogram is not None:
            if histogram > 0: result.bull += weight * 0.25
            elif histogram < 0: result.bear += weight * 0.25
        return self._bounded(result, weight)

    def score_volume(self, technical: Mapping[str, Any] | None) -> DirectionalScore:
        data, weight, result = self._indicators(technical), self.config.volume_weight, DirectionalScore()
        volume, average = self._number(data, "VOLUME"), self._number(data, "VOLUME_EMA20")
        price, vwap = self._number(data, "CURRENT_PRICE"), self._number(data, "VWAP")
        if volume is not None and average is not None and average > 0:
            if volume >= average:
                if price is not None and vwap is not None and price >= vwap: result.bull += weight * 0.7; result.reasons.append("Above-average volume supports buyers")
                elif price is not None and vwap is not None: result.bear += weight * 0.7; result.reasons.append("Above-average volume supports sellers")
            else: result.bull += weight * 0.1; result.bear += weight * 0.1; result.reasons.append("Volume conviction is limited")
        if price is not None and vwap is not None:
            if price > vwap: result.bull += weight * 0.3
            elif price < vwap: result.bear += weight * 0.3
        return self._bounded(result, weight)

    def score_price_action(self, technical: Mapping[str, Any] | None) -> DirectionalScore:
        data, weight, result = self._indicators(technical), self.config.price_action_weight, DirectionalScore()
        if self._flag(data, "BREAKOUT"): result.bull += weight * 0.4; result.reasons.append("Confirmed upside breakout")
        if self._flag(data, "BREAKDOWN"): result.bear += weight * 0.4; result.reasons.append("Confirmed downside breakdown")
        if self._flag(data, "HIGHER_HIGH") and self._flag(data, "HIGHER_LOW"): result.bull += weight * 0.4; result.reasons.append("Higher-high/higher-low structure")
        if self._flag(data, "LOWER_HIGH") and self._flag(data, "LOWER_LOW"): result.bear += weight * 0.4; result.reasons.append("Lower-high/lower-low structure")
        if self._flag(data, "BULLISH_PATTERN"): result.bull += weight * 0.2; result.reasons.append("Bullish price pattern detected")
        if self._flag(data, "BEARISH_PATTERN"): result.bear += weight * 0.2; result.reasons.append("Bearish price pattern detected")
        return self._bounded(result, weight)

    def score_volatility(self, technical: Mapping[str, Any] | None) -> DirectionalScore:
        data, weight, result = self._indicators(technical), self.config.volatility_weight, DirectionalScore()
        vix = self._number(data, "INDIA_VIX")
        if vix is None: return result
        if vix >= self.config.vix_extreme: result.bear += weight; result.reasons.append("Extreme India VIX increases downside risk")
        elif vix >= self.config.vix_elevated: result.bear += weight * 0.6; result.bull += weight * 0.1; result.reasons.append("Elevated India VIX reduces directional confidence")
        else: result.bull += weight * 0.35; result.bear += weight * 0.35; result.reasons.append("Orderly India VIX environment")
        return self._bounded(result, weight)

    def score_market_context(self, technical: Mapping[str, Any] | None) -> DirectionalScore:
        data, weight, result = self._indicators(technical), self.config.context_weight, DirectionalScore()
        gap = self._number(data, "GAP_PERCENT")
        trend_day = str(data.get("TREND_DAY", "")).strip().upper()
        if trend_day in {"BULLISH", "UP", "UPTREND"}: result.bull += weight * 0.6; result.reasons.append("Bullish trend-day context")
        elif trend_day in {"BEARISH", "DOWN", "DOWNTREND"}: result.bear += weight * 0.6; result.reasons.append("Bearish trend-day context")
        if gap is not None:
            if gap >= self.config.gap_threshold: result.bull += weight * 0.4; result.reasons.append("Positive opening gap")
            elif gap <= -self.config.gap_threshold: result.bear += weight * 0.4; result.reasons.append("Negative opening gap")
        return self._bounded(result, weight)

    @staticmethod
    def calculate_confidence(bull_score: float, bear_score: float, available_categories: int) -> float:
        coverage = min(1.0, available_categories / 6.0)
        return round(min(100.0, abs(bull_score - bear_score) * coverage), 2)

    def market_score(self, technical: Mapping[str, Any] | None) -> dict[str, Any]:
        categories = {"trend": self.score_trend(technical), "momentum": self.score_momentum(technical), "volume": self.score_volume(technical), "price_action": self.score_price_action(technical), "volatility": self.score_volatility(technical), "market_context": self.score_market_context(technical)}
        bull, bear = (round(sum(item.bull for item in categories.values()), 2), round(sum(item.bear for item in categories.values()), 2))
        confidence = self.calculate_confidence(bull, bear, sum(bool(item.reasons) for item in categories.values()))
        trend = "BULLISH" if bull > bear else "BEARISH" if bear > bull else "SIDEWAYS"
        reasons = [reason for item in categories.values() for reason in item.reasons]
        return {"bull_score": bull, "bear_score": bear, "bull": bull, "bear": bear, "market_score": round(bull - bear, 2), "score": round(bull - bear, 2), "trend": trend, "confidence": confidence, "category_scores": {name: {"bull_score": score.bull, "bear_score": score.bear} for name, score in categories.items()}, "reasons": reasons}


def market_score(technical: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Compatibility entry point for :class:`MarketScoreEngine`."""
    return MarketScoreEngine().market_score(technical)
