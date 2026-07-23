"""Final trade-quality assessment over completed analysis-engine outputs."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TradeQualityConfig:
    trade_threshold: float = 70.0
    high_vix: float = 20.0
    extreme_vix: float = 28.0
    strong_adx: float = 25.0
    volume_confirmation_ratio: float = 1.0
    strong_confidence: float = 75.0
    strong_alignment: float = 75.0
    minimum_risk_reward: float = 1.5
    weights: tuple[tuple[str, float], ...] = (
        ("trend", 0.18), ("momentum", 0.12), ("volume", 0.10),
        ("price_action", 0.10), ("volatility", 0.08), ("options", 0.12),
        ("sentiment", 0.05), ("confidence", 0.10), ("market_regime", 0.08),
        ("timeframe_alignment", 0.10), ("risk_reward", 0.07),
    )


class TradeQualityEngine:
    """Evaluate whether an already-proposed trade has sufficient execution quality."""

    def __init__(self, config: TradeQualityConfig | None = None) -> None:
        self.config = config or TradeQualityConfig()

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
    def _direction(value: Any) -> str | None:
        text = str(value or "").strip().upper()
        if text in {"BUY", "BULL", "BULLISH", "LONG", "UP", "UPTREND"}: return "BULLISH"
        if text in {"SELL", "BEAR", "BEARISH", "SHORT", "DOWN", "DOWNTREND"}: return "BEARISH"
        if text in {"HOLD", "WAIT", "NEUTRAL", "SIDEWAYS", "RANGE"}: return "NEUTRAL"
        return None

    def _score_direction(self, data: Mapping[str, Any], fallback: str | None = None) -> tuple[str | None, float]:
        bull, bear = self._number(data, "bull_score", "bull"), self._number(data, "bear_score", "bear")
        if bull is not None and bear is not None and bull + bear > 0:
            delta = (bull - bear) * 100.0 / (bull + bear)
            return ("NEUTRAL" if abs(delta) < 5 else "BULLISH" if delta > 0 else "BEARISH"), abs(delta)
        direction = self._direction(data.get(fallback)) if fallback else None
        return direction, 50.0 if direction else 0.0

    @staticmethod
    def _indicators(technical: Mapping[str, Any]) -> Mapping[str, Any]:
        nested = technical.get("indicators")
        return nested if isinstance(nested, Mapping) else technical

    def evaluate(self, technical: Mapping[str, Any] | None = None, market: Mapping[str, Any] | None = None, option: Mapping[str, Any] | None = None, sentiment: Mapping[str, Any] | None = None, strategy: Mapping[str, Any] | None = None, confidence: Mapping[str, Any] | float | int | None = None, market_regime: Mapping[str, Any] | None = None, decision_validator: Mapping[str, Any] | None = None, multi_timeframe: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return a quality grade without calculating or fetching market data."""
        try:
            return self._evaluate(technical, market, option, sentiment, strategy, confidence, market_regime, decision_validator, multi_timeframe)
        except Exception as exc:
            logger.exception("Trade-quality evaluation failed")
            return self._failure_result(f"Trade-quality evaluation failed: {type(exc).__name__}.")

    def _evaluate(self, technical: Mapping[str, Any] | None, market: Mapping[str, Any] | None, option: Mapping[str, Any] | None, sentiment: Mapping[str, Any] | None, strategy: Mapping[str, Any] | None, confidence: Mapping[str, Any] | float | int | None, market_regime: Mapping[str, Any] | None, decision_validator: Mapping[str, Any] | None, multi_timeframe: Mapping[str, Any] | None) -> dict[str, Any]:
        technical_data, market_data, option_data = self._mapping(technical), self._mapping(market), self._mapping(option)
        sentiment_data, strategy_data, regime_data = self._mapping(sentiment), self._mapping(strategy), self._mapping(market_regime)
        validator_data, mtf_data = self._mapping(decision_validator), self._mapping(multi_timeframe)
        indicators = self._indicators(technical_data)
        proposed = self._direction(strategy_data.get("signal", strategy_data.get("recommendation")))
        technical_direction, technical_strength = self._score_direction(technical_data, "trend")
        market_direction, market_strength = self._score_direction(market_data, "trend")
        option_direction, option_strength = self._score_direction(option_data)
        sentiment_direction, sentiment_strength = self._score_direction(sentiment_data, "summary")
        strengths: list[str] = []
        weaknesses: list[str] = []
        reasons: list[str] = []
        trend_score = self._trend_score(proposed, technical_direction, technical_strength, market_direction, market_strength, regime_data, strengths, weaknesses)
        momentum_score = self._momentum_score(indicators, proposed, strengths, weaknesses)
        volume_score = self._volume_score(indicators, strengths, weaknesses)
        price_action_score = self._price_action_score(indicators, proposed, strengths, weaknesses)
        volatility_score = self._volatility_score(indicators, strengths, weaknesses)
        option_score = self._confirmation_score("Option chain", option_data, option_direction, option_strength, proposed, strengths, weaknesses)
        sentiment_score = self._confirmation_score("Sentiment", sentiment_data, sentiment_direction, sentiment_strength, proposed, strengths, weaknesses)
        confidence_value = self._confidence_value(confidence)
        confidence_score = self._clamp(confidence_value or 0.0)
        if confidence_value is None: weaknesses.append("Confidence output is missing")
        elif confidence_value >= self.config.strong_confidence: strengths.append("Confidence is strong")
        else: weaknesses.append("Confidence is below the strong-quality threshold")
        regime_score = self._regime_score(regime_data, proposed, strengths, weaknesses)
        timeframe_score = self._timeframe_score(mtf_data, proposed, strengths, weaknesses)
        risk_reward_score, risk_level, reward_potential = self._risk_reward_score(strategy_data, indicators, proposed, volatility_score, strengths, weaknesses)
        scores = {"trend": trend_score, "momentum": momentum_score, "volume": volume_score, "price_action": price_action_score, "volatility": volatility_score, "options": option_score, "sentiment": sentiment_score, "confidence": confidence_score, "market_regime": regime_score, "timeframe_alignment": timeframe_score, "risk_reward": risk_reward_score}
        total_weight = sum(weight for _, weight in self.config.weights)
        overall = self._clamp(sum(scores[name] * weight for name, weight in self.config.weights) / total_weight)
        validator_approved = validator_data.get("approved") is True
        validator_status = str(validator_data.get("status", "")).upper()
        if not validator_data:
            weaknesses.append("Decision-validator output is missing")
            reasons.append("Do not trade: final validation gate is unavailable.")
        elif not validator_approved:
            weaknesses.append("Decision validator did not approve the trade")
            reasons.append("Do not trade: final validation gate rejected or cautioned the proposal.")
            overall = min(overall, 49.0 if validator_status == "REJECTED" else 59.0)
        if proposed not in {"BULLISH", "BEARISH"}:
            weaknesses.append("Strategy does not contain an actionable BUY or SELL direction")
            overall = min(overall, 35.0)
        should_trade = validator_approved and proposed in {"BULLISH", "BEARISH"} and overall >= self.config.trade_threshold and risk_reward_score >= self.config.minimum_risk_reward * 20.0
        grade = self._grade(overall)
        trade_class = self._trade_class(overall, should_trade)
        recommendation = self._recommendation(should_trade, validator_approved, overall, proposed, risk_reward_score)
        reasons.insert(0, recommendation)
        return {"overall_score": overall, "grade": grade, "trade_class": trade_class, "should_trade": should_trade, "strengths": list(dict.fromkeys(strengths)), "weaknesses": list(dict.fromkeys(weaknesses)), "risk_level": risk_level, "reward_potential": reward_potential, "category_scores": {**scores, "overall": overall}, "recommendation_reason": recommendation, "reasons": list(dict.fromkeys(reasons))}

    def _trend_score(self, proposed: str | None, technical_direction: str | None, technical_strength: float, market_direction: str | None, market_strength: float, regime: Mapping[str, Any], strengths: list[str], weaknesses: list[str]) -> float:
        if proposed not in {"BULLISH", "BEARISH"}: return 0.0
        score = 0.0
        if technical_direction == proposed: score += 35 + technical_strength * 0.15
        if market_direction == proposed: score += 35 + market_strength * 0.15
        regime_name = str(regime.get("regime", "")).upper()
        compatible = {"BULLISH": {"TRENDING_BULL", "BREAKOUT", "GAP_UP_TREND_DAY", "PULLBACK_TREND"}, "BEARISH": {"TRENDING_BEAR", "BREAKDOWN", "GAP_DOWN_TREND_DAY", "PULLBACK_TREND"}}
        if regime_name in compatible[proposed]: score += 20
        if score >= 70: strengths.append("Technical, market, and regime trend direction align")
        else: weaknesses.append("Trend alignment is incomplete")
        return self._clamp(score)

    def _momentum_score(self, indicators: Mapping[str, Any], proposed: str | None, strengths: list[str], weaknesses: list[str]) -> float:
        rsi, macd, signal, adx = (self._number(indicators, key) for key in ("RSI", "MACD", "MACD_SIGNAL", "ADX"))
        if proposed not in {"BULLISH", "BEARISH"}: return 0.0
        score = 0.0
        if (proposed == "BULLISH" and rsi is not None and rsi >= 55) or (proposed == "BEARISH" and rsi is not None and rsi <= 45): score += 35
        if (proposed == "BULLISH" and macd is not None and signal is not None and macd > signal) or (proposed == "BEARISH" and macd is not None and signal is not None and macd < signal): score += 40
        if adx is not None and adx >= self.config.strong_adx: score += 25
        (strengths if score >= 70 else weaknesses).append("Momentum confirms direction" if score >= 70 else "Momentum confirmation is weak or incomplete")
        return self._clamp(score)

    def _volume_score(self, indicators: Mapping[str, Any], strengths: list[str], weaknesses: list[str]) -> float:
        volume, average = self._number(indicators, "VOLUME"), self._number(indicators, "VOLUME_EMA20")
        if volume is None or average is None or average <= 0: weaknesses.append("Volume data is unavailable"); return 0.0
        ratio = volume / average
        score = self._clamp(ratio * 70.0)
        (strengths if ratio >= self.config.volume_confirmation_ratio else weaknesses).append("Volume confirms participation" if ratio >= self.config.volume_confirmation_ratio else "Volume is below confirmation level")
        return score

    def _price_action_score(self, indicators: Mapping[str, Any], proposed: str | None, strengths: list[str], weaknesses: list[str]) -> float:
        true = lambda key: indicators.get(key) is True or str(indicators.get(key, "")).upper() in {"TRUE", "YES", "1", "BULLISH"}
        score = 0.0
        if proposed == "BULLISH": score = 60.0 if true("BREAKOUT") else 40.0 if true("HIGHER_HIGH") and true("HIGHER_LOW") else 0.0
        elif proposed == "BEARISH": score = 60.0 if true("BREAKDOWN") else 40.0 if true("LOWER_HIGH") and true("LOWER_LOW") else 0.0
        (strengths if score >= 40 else weaknesses).append("Price action supports direction" if score >= 40 else "No supporting price-action structure")
        return score

    def _volatility_score(self, indicators: Mapping[str, Any], strengths: list[str], weaknesses: list[str]) -> float:
        vix = self._number(indicators, "INDIA_VIX")
        if vix is None: weaknesses.append("India VIX is unavailable"); return 50.0
        score = 100.0 if vix < self.config.high_vix else 45.0 if vix < self.config.extreme_vix else 15.0
        (strengths if score >= 70 else weaknesses).append("Volatility environment is controlled" if score >= 70 else "Volatility environment elevates execution risk")
        return score

    def _confirmation_score(self, label: str, data: Mapping[str, Any], direction: str | None, strength: float, proposed: str | None, strengths: list[str], weaknesses: list[str]) -> float:
        if not data or direction is None: weaknesses.append(f"{label} confirmation is unavailable"); return 0.0
        if direction == proposed: strengths.append(f"{label} confirms strategy direction"); return self._clamp(50.0 + strength / 2.0)
        if direction == "NEUTRAL": weaknesses.append(f"{label} is neutral"); return 40.0
        weaknesses.append(f"{label} contradicts strategy direction"); return 0.0

    def _regime_score(self, regime: Mapping[str, Any], proposed: str | None, strengths: list[str], weaknesses: list[str]) -> float:
        name = str(regime.get("regime", "")).upper()
        if not name: weaknesses.append("Market regime is unavailable"); return 0.0
        supported = {"BULLISH": {"TRENDING_BULL", "BREAKOUT", "GAP_UP_TREND_DAY", "PULLBACK_TREND"}, "BEARISH": {"TRENDING_BEAR", "BREAKDOWN", "GAP_DOWN_TREND_DAY", "PULLBACK_TREND"}}
        if proposed in supported and name in supported[proposed]: strengths.append("Market regime supports trade direction"); return self._clamp(self._number(regime, "confidence") or 75.0)
        weaknesses.append("Market regime does not support trade direction"); return 20.0 if name in {"SIDEWAYS", "RANGE_BOUND"} else 0.0

    def _timeframe_score(self, mtf: Mapping[str, Any], proposed: str | None, strengths: list[str], weaknesses: list[str]) -> float:
        alignment = self._number(mtf, "alignment_percent")
        direction = self._direction(mtf.get("overall_trend"))
        if alignment is None: weaknesses.append("Multi-timeframe alignment is unavailable"); return 0.0
        if direction == proposed: strengths.append("Multi-timeframe analysis aligns with strategy"); return self._clamp(alignment)
        weaknesses.append("Multi-timeframe trend does not align with strategy"); return self._clamp(alignment * 0.25)

    def _risk_reward_score(self, strategy: Mapping[str, Any], indicators: Mapping[str, Any], proposed: str | None, volatility_score: float, strengths: list[str], weaknesses: list[str]) -> tuple[float, str, str]:
        entry = self._number(strategy, "entry", "ENTRY") or self._number(indicators, "ENTRY", "CURRENT_PRICE")
        stop = self._number(strategy, "stop_loss", "STOP_LOSS") or self._number(indicators, "STOP_LOSS")
        target = self._number(strategy, "target1", "TARGET1", "target") or self._number(indicators, "TARGET1")
        if proposed not in {"BULLISH", "BEARISH"} or None in (entry, stop, target): weaknesses.append("Risk/reward levels are incomplete"); return 0.0, "HIGH", "LOW"
        risk, reward = (entry - stop, target - entry) if proposed == "BULLISH" else (stop - entry, entry - target)
        if risk <= 0 or reward <= 0: weaknesses.append("Risk/reward levels are invalid for strategy direction"); return 0.0, "HIGH", "LOW"
        ratio = reward / risk
        score = self._clamp(ratio * 40.0)
        if ratio >= 2.0: strengths.append(f"Risk/reward is favourable at {ratio:.2f}R")
        else: weaknesses.append(f"Risk/reward is limited at {ratio:.2f}R")
        risk_level = "LOW" if ratio >= 2 and volatility_score >= 70 else "MEDIUM" if ratio >= 1 else "HIGH"
        reward_potential = "HIGH" if ratio >= 2 else "MEDIUM" if ratio >= 1 else "LOW"
        return score, risk_level, reward_potential

    def _confidence_value(self, confidence: Mapping[str, Any] | float | int | None) -> float | None:
        if isinstance(confidence, Mapping): return self._number(confidence, "confidence")
        try:
            value = float(confidence)
            return value if math.isfinite(value) else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _grade(score: float) -> str:
        return "A+" if score >= 90 else "A" if score >= 80 else "B+" if score >= 70 else "B" if score >= 60 else "C" if score >= 50 else "D" if score >= 40 else "F"

    @staticmethod
    def _trade_class(score: float, should_trade: bool) -> str:
        if not should_trade: return "AVOID"
        return "ELITE" if score >= 90 else "HIGH_QUALITY" if score >= 80 else "GOOD" if score >= 70 else "AVERAGE" if score >= 60 else "LOW_QUALITY"

    @staticmethod
    def _recommendation(should_trade: bool, validator_approved: bool, score: float, direction: str | None, risk_reward: float) -> str:
        if not validator_approved: return "Avoid trade: the final decision validator has not approved it."
        if direction not in {"BULLISH", "BEARISH"}: return "Avoid trade: no actionable strategy direction is present."
        if risk_reward < 30.0: return "Avoid trade: risk/reward is below the configured minimum."
        if should_trade: return f"Trade approved: {direction.lower()} confluence and quality score meet the execution threshold."
        return f"Do not trade yet: quality score {score:.2f} is below the configured threshold."

    @staticmethod
    def _failure_result(reason: str) -> dict[str, Any]:
        return {"overall_score": 0.0, "grade": "F", "trade_class": "AVOID", "should_trade": False, "strengths": [], "weaknesses": [reason], "risk_level": "HIGH", "reward_potential": "LOW", "category_scores": {"overall": 0.0}, "recommendation_reason": reason, "reasons": [reason]}


def evaluate_trade_quality(technical: Mapping[str, Any] | None = None, market: Mapping[str, Any] | None = None, option: Mapping[str, Any] | None = None, sentiment: Mapping[str, Any] | None = None, strategy: Mapping[str, Any] | None = None, confidence: Mapping[str, Any] | float | int | None = None, market_regime: Mapping[str, Any] | None = None, decision_validator: Mapping[str, Any] | None = None, multi_timeframe: Mapping[str, Any] | None = None, config: TradeQualityConfig | None = None) -> dict[str, Any]:
    """Convenience entry point for final trade-quality evaluation."""
    return TradeQualityEngine(config).evaluate(technical, market, option, sentiment, strategy, confidence, market_regime, decision_validator, multi_timeframe)
