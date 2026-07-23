"""Snapshot-only market-regime classifier for trade-decision pipelines."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MarketRegimeConfig:
    strong_adx: float = 25.0
    weak_adx: float = 20.0
    high_atr_percent: float = 1.5
    low_atr_percent: float = 0.5
    elevated_vix: float = 20.0
    extreme_vix: float = 28.0
    trend_day_gap_percent: float = 0.5
    overbought_rsi: float = 70.0
    oversold_rsi: float = 30.0
    exhaustion_rsi: float = 75.0
    pullback_tolerance_percent: float = 0.5


class MarketRegimeEngine:
    """Classify a supplied technical snapshot without computing indicators."""

    def __init__(self, config: MarketRegimeConfig | None = None) -> None:
        self.config = config or MarketRegimeConfig()

    @staticmethod
    def _snapshot(technical: Mapping[str, Any] | None) -> Mapping[str, Any]:
        if not isinstance(technical, Mapping):
            return {}
        nested = technical.get("indicators")
        return nested if isinstance(nested, Mapping) else technical

    @staticmethod
    def _number(data: Mapping[str, Any], name: str) -> float | None:
        try:
            number = float(data.get(name))
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @staticmethod
    def _flag(data: Mapping[str, Any], name: str) -> bool:
        value = data.get(name, False)
        return value is True or str(value).strip().upper() in {"TRUE", "YES", "1", "BULLISH"}

    @staticmethod
    def _clamp(value: float) -> float:
        return round(min(100.0, max(0.0, value)), 2)

    def _trend_direction(self, data: Mapping[str, Any], reasons: list[str]) -> str:
        price, ema20, ema50, ema200 = (self._number(data, key) for key in ("CURRENT_PRICE", "EMA20", "EMA50", "EMA200"))
        higher_structure = self._flag(data, "HIGHER_HIGH") and self._flag(data, "HIGHER_LOW")
        lower_structure = self._flag(data, "LOWER_HIGH") and self._flag(data, "LOWER_LOW")
        if None not in (price, ema20, ema50, ema200) and price > ema20 > ema50 > ema200:
            reasons.append("Price and EMA alignment are bullish.")
            return "BULLISH"
        if None not in (price, ema20, ema50, ema200) and price < ema20 < ema50 < ema200:
            reasons.append("Price and EMA alignment are bearish.")
            return "BEARISH"
        if higher_structure:
            reasons.append("Higher-high and higher-low structure is bullish.")
            return "BULLISH"
        if lower_structure:
            reasons.append("Lower-high and lower-low structure is bearish.")
            return "BEARISH"
        reasons.append("EMA and price structure do not establish a directional trend.")
        return "NEUTRAL"

    def _trend_strength(self, data: Mapping[str, Any], direction: str) -> float:
        adx = self._number(data, "ADX")
        if adx is None:
            return 0.0
        strength = min(70.0, max(0.0, adx / 50.0 * 70.0))
        if direction != "NEUTRAL":
            strength += 15.0
        if (direction == "BULLISH" and self._flag(data, "HIGHER_HIGH") and self._flag(data, "HIGHER_LOW")) or (direction == "BEARISH" and self._flag(data, "LOWER_HIGH") and self._flag(data, "LOWER_LOW")):
            strength += 15.0
        return self._clamp(strength)

    def _volatility(self, data: Mapping[str, Any], reasons: list[str]) -> float:
        price, atr, vix = self._number(data, "CURRENT_PRICE"), self._number(data, "ATR"), self._number(data, "INDIA_VIX")
        atr_component = 0.0
        if price is not None and price > 0 and atr is not None:
            atr_percent = atr * 100.0 / price
            atr_component = min(100.0, atr_percent * 100.0 / self.config.high_atr_percent)
            reasons.append(f"ATR is {atr_percent:.2f}% of current price.")
        vix_component = 0.0
        if vix is not None:
            vix_component = min(100.0, vix * 100.0 / self.config.extreme_vix)
            reasons.append(f"India VIX is {vix:.2f}.")
        return self._clamp(max(atr_component, vix_component))

    def _range_strength(self, data: Mapping[str, Any], direction: str) -> float:
        adx, price, support, resistance = (self._number(data, key) for key in ("ADX", "CURRENT_PRICE", "SUPPORT", "RESISTANCE"))
        score = 35.0 if direction == "NEUTRAL" else 0.0
        if adx is not None:
            score += max(0.0, (self.config.strong_adx - adx) * 2.0)
        if None not in (price, support, resistance) and resistance > support and support <= price <= resistance:
            midpoint = (support + resistance) / 2.0
            half_range = (resistance - support) / 2.0
            if half_range > 0:
                score += max(0.0, 30.0 * (1.0 - abs(price - midpoint) / half_range))
        return self._clamp(score)

    def _breakout_probability(self, data: Mapping[str, Any], direction: str) -> float:
        price, resistance, support = (self._number(data, key) for key in ("CURRENT_PRICE", "RESISTANCE", "SUPPORT"))
        volume, average = self._number(data, "VOLUME"), self._number(data, "VOLUME_EMA20")
        score = 0.0
        if self._flag(data, "BREAKOUT") or self._flag(data, "BREAKDOWN"):
            score += 55.0
        if direction == "BULLISH" and price is not None and resistance is not None and price >= resistance:
            score += 25.0
        elif direction == "BEARISH" and price is not None and support is not None and price <= support:
            score += 25.0
        if volume is not None and average is not None and average > 0 and volume >= average:
            score += 20.0
        return self._clamp(score)

    def _is_pullback(self, data: Mapping[str, Any], direction: str) -> bool:
        price, ema20, ema50 = (self._number(data, key) for key in ("CURRENT_PRICE", "EMA20", "EMA50"))
        if None in (price, ema20, ema50) or price <= 0:
            return False
        tolerance = price * self.config.pullback_tolerance_percent / 100.0
        if direction == "BULLISH":
            return ema50 <= price <= ema20 + tolerance
        if direction == "BEARISH":
            return ema20 - tolerance <= price <= ema50
        return False

    def classify(self, technical: Mapping[str, Any] | None) -> dict[str, Any]:
        """Classify the supplied snapshot and return stable, bounded metrics."""
        try:
            data = self._snapshot(technical)
            if not data:
                return self._empty_result("Technical snapshot is missing.")
            reasons: list[str] = []
            direction = self._trend_direction(data, reasons)
            trend_strength = self._trend_strength(data, direction)
            volatility = self._volatility(data, reasons)
            range_strength = self._range_strength(data, direction)
            breakout_probability = self._breakout_probability(data, direction)
            adx, rsi, gap, vix = (self._number(data, key) for key in ("ADX", "RSI", "GAP_PERCENT", "INDIA_VIX"))
            breakout, breakdown = self._flag(data, "BREAKOUT"), self._flag(data, "BREAKDOWN")
            if gap is not None and gap >= self.config.trend_day_gap_percent and direction == "BULLISH" and trend_strength >= 50:
                regime = "GAP_UP_TREND_DAY"; reasons.append("Positive gap aligns with a strong bullish trend.")
            elif gap is not None and gap <= -self.config.trend_day_gap_percent and direction == "BEARISH" and trend_strength >= 50:
                regime = "GAP_DOWN_TREND_DAY"; reasons.append("Negative gap aligns with a strong bearish trend.")
            elif breakout and direction == "BULLISH":
                regime = "BREAKOUT"; reasons.append("Confirmed upside breakout is present in the snapshot.")
            elif breakdown and direction == "BEARISH":
                regime = "BREAKDOWN"; reasons.append("Confirmed downside breakdown is present in the snapshot.")
            elif direction != "NEUTRAL" and rsi is not None and ((direction == "BULLISH" and rsi >= self.config.exhaustion_rsi) or (direction == "BEARISH" and rsi <= 100.0 - self.config.exhaustion_rsi)):
                regime = "EXHAUSTION_TREND"; reasons.append("Trend direction and extreme RSI indicate possible exhaustion.")
            elif self._is_pullback(data, direction) and trend_strength >= 50:
                regime = "PULLBACK_TREND"; reasons.append("Price is retracing within an established trend structure.")
            elif direction == "NEUTRAL" and rsi is not None and (rsi >= self.config.overbought_rsi or rsi <= self.config.oversold_rsi):
                regime = "MEAN_REVERSION"; reasons.append("Weak trend with an RSI extreme favours mean reversion.")
            elif volatility >= 70 or (vix is not None and vix >= self.config.extreme_vix):
                regime = "HIGH_VOLATILITY"; reasons.append("ATR or India VIX indicates high volatility.")
            elif volatility <= 30:
                regime = "LOW_VOLATILITY"; reasons.append("ATR and India VIX indicate low volatility.")
            elif direction == "BULLISH" and trend_strength >= 50:
                regime = "TRENDING_BULL"; reasons.append("Bullish structure is supported by trend strength.")
            elif direction == "BEARISH" and trend_strength >= 50:
                regime = "TRENDING_BEAR"; reasons.append("Bearish structure is supported by trend strength.")
            elif range_strength >= 55:
                regime = "RANGE_BOUND"; reasons.append("Low trend strength and support/resistance behaviour indicate a range.")
            else:
                regime = "SIDEWAYS"; reasons.append("No dominant trend or range condition is sufficiently confirmed.")
            evidence = sum(value is not None for value in (adx, rsi, gap, vix, self._number(data, "ATR"), self._number(data, "CURRENT_PRICE")))
            confidence = 35.0 + evidence * 7.0
            if regime in {"TRENDING_BULL", "TRENDING_BEAR", "GAP_UP_TREND_DAY", "GAP_DOWN_TREND_DAY", "BREAKOUT", "BREAKDOWN"}:
                confidence += trend_strength * 0.25 + breakout_probability * 0.2
            elif regime in {"RANGE_BOUND", "MEAN_REVERSION", "SIDEWAYS"}:
                confidence += range_strength * 0.3
            else:
                confidence += volatility * 0.25
            return {"regime": regime, "confidence": self._clamp(confidence), "trend_strength": trend_strength, "volatility": volatility, "range_strength": range_strength, "breakout_probability": breakout_probability, "reasons": reasons}
        except Exception as exc:
            logger.exception("Market-regime classification failed")
            return self._empty_result(f"Regime classification failed: {type(exc).__name__}.")

    def _empty_result(self, reason: str) -> dict[str, Any]:
        return {"regime": "SIDEWAYS", "confidence": 0.0, "trend_strength": 0.0, "volatility": 0.0, "range_strength": 0.0, "breakout_probability": 0.0, "reasons": [reason]}


def market_regime(technical: Mapping[str, Any] | None) -> dict[str, Any]:
    """Compatibility entry point for snapshot-only regime classification."""
    return MarketRegimeEngine().classify(technical)


def analyze_market_regime(technical: Mapping[str, Any] | None) -> dict[str, Any]:
    """American-English alias used by decision-pipeline integrations."""
    return market_regime(technical)
