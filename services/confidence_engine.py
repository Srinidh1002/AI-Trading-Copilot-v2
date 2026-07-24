"""Trade-confidence validation based on cross-engine confluence.

The engine consumes completed analysis payloads.  It never calculates market
indicators or fetches data; its sole responsibility is deciding how strongly
the independent analysis engines agree with the proposed strategy direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import math
from collections.abc import Mapping
from typing import Any
from services.adaptive_confidence_engine import (
    adaptive_confidence_engine,
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConfidenceConfig:
    """Explicit confluence thresholds and bounded score adjustments."""

    neutral_score_band: float = 5.0
    high_adx: float = 25.0
    high_vix: float = 20.0
    extreme_vix: float = 28.0
    strong_volume_ratio: float = 1.0
    agreement_points: float = 10.0
    all_agree_bonus: float = 20.0
    strong_trend_bonus: float = 8.0
    high_adx_bonus: float = 7.0
    high_volume_bonus: float = 6.0
    vwap_bonus: float = 5.0
    breakout_bonus: float = 7.0
    option_confirmation_bonus: float = 8.0
    strong_sentiment_bonus: float = 5.0
    weak_adx_penalty: float = 8.0
    low_volume_penalty: float = 6.0
    high_vix_penalty: float = 8.0
    extreme_vix_penalty: float = 15.0
    range_penalty: float = 10.0
    missing_option_penalty: float = 12.0
    missing_sentiment_penalty: float = 8.0
    conflict_penalty: float = 12.0
    hold_confidence_cap: float = 35.0


@dataclass(slots=True)
class EngineSignal:
    """Normalized directional evidence extracted from one engine payload."""

    direction: str | None = None
    strength: float = 0.0
    available: bool = False
    details: list[str] = field(default_factory=list)


class ConfidenceEngine:
    """Assess trade quality through agreement, confirmations, and risk flags."""

    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self.config = config or ConfidenceConfig()

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
    def _truthy(data: Mapping[str, Any], key: str) -> bool:
        value = data.get(key, False)
        return value is True or str(value).strip().upper() in {"TRUE", "YES", "1", "BULLISH"}

    def _from_scores(self, data: Mapping[str, Any]) -> EngineSignal:
        bull = self._number(data, "bull_score", "bull")
        bear = self._number(data, "bear_score", "bear")
        if bull is None or bear is None or bull < 0 or bear < 0 or bull + bear <= 0:
            return EngineSignal()
        total = bull + bear
        difference = (bull - bear) * 100.0 / total
        if abs(difference) <= self.config.neutral_score_band:
            direction = "NEUTRAL"
        else:
            direction = "BULLISH" if difference > 0 else "BEARISH"
        return EngineSignal(direction=direction, strength=round(abs(difference), 2), available=True)

    @staticmethod
    def _normalise_direction(value: Any) -> str | None:
        text = str(value or "").strip().upper()
        if text in {"BUY", "BULL", "BULLISH", "UP", "UPTREND", "LONG"}:
            return "BULLISH"
        if text in {"SELL", "BEAR", "BEARISH", "DOWN", "DOWNTREND", "SHORT"}:
            return "BEARISH"
        if text in {"HOLD", "WAIT", "NEUTRAL", "SIDEWAYS", "RANGE", "UNKNOWN"}:
            return "NEUTRAL"
        return None

    def _technical_signal(self, technical: Mapping[str, Any]) -> EngineSignal:
        signal = self._from_scores(technical)
        indicators = self._mapping(technical.get("indicators")) or technical
        if signal.available:
            return signal
        ema20, ema50, ema200 = (self._number(indicators, key) for key in ("EMA20", "EMA50", "EMA200"))
        if None not in (ema20, ema50, ema200):
            if ema20 > ema50 > ema200:
                return EngineSignal("BULLISH", 70.0, True, ["EMA alignment is bullish"])
            if ema20 < ema50 < ema200:
                return EngineSignal("BEARISH", 70.0, True, ["EMA alignment is bearish"])
        return EngineSignal()

    def _market_signal(self, market: Mapping[str, Any]) -> EngineSignal:
        signal = self._from_scores(market)
        if signal.available:
            return signal
        direction = self._normalise_direction(market.get("trend"))
        return EngineSignal(direction, 50.0, direction is not None) if direction else EngineSignal()

    def _option_signal(self, option: Mapping[str, Any]) -> EngineSignal:
        signal = self._from_scores(option)
        if signal.available:
            return signal
        pcr = self._number(option, "PCR", "pcr")
        if pcr is None:
            return EngineSignal()
        if pcr > 1.0:
            return EngineSignal("BULLISH", min(100.0, (pcr - 1.0) * 100.0), True)
        if pcr < 1.0:
            return EngineSignal("BEARISH", min(100.0, (1.0 - pcr) * 100.0), True)
        return EngineSignal("NEUTRAL", 0.0, True)

    def _sentiment_signal(self, sentiment: Mapping[str, Any]) -> EngineSignal:
        signal = self._from_scores(sentiment)
        if signal.available:
            return signal
        direction = self._normalise_direction(sentiment.get("summary", sentiment.get("sentiment")))
        score = self._number(sentiment, "score", "confidence")
        if direction is None or score is None:
            return EngineSignal()
        strength = abs(score - 50.0) * 2.0
        return EngineSignal(direction, round(strength, 2), True)

    def _strategy_signal(self, strategy: Mapping[str, Any]) -> EngineSignal:
        action = str(strategy.get("signal", strategy.get("recommendation", ""))).strip().upper()
        direction = self._normalise_direction(action)
        return EngineSignal(direction, 100.0, direction is not None, [action] if action else [])

    @staticmethod
    def _indicators(technical: Mapping[str, Any]) -> Mapping[str, Any]:
        nested = technical.get("indicators")
        return nested if isinstance(nested, Mapping) else technical

    def _append_confirmation(self, condition: bool, bonus: float, message: str, score: float, strengths: list[str], reasons: list[str]) -> float:
        if condition:
            strengths.append(message)
            reasons.append(f"Confidence increased: {message}.")
            return score + bonus
        return score

    def evaluate(
        self,
            technical: Mapping[str, Any] | None,
            market: Mapping[str, Any] | None,
            option: Mapping[str, Any] | None,
            sentiment: Mapping[str, Any] | None,
            strategy: Mapping[str, Any] | None,
            smart_money: Mapping[str, Any] | None,
            risk: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a bounded confidence assessment without raising to callers."""
        try:
            return self._evaluate(technical, market, option, sentiment, strategy, smart_money, risk)
        except Exception as exc:
            logger.exception("Confidence evaluation failed")
            return self._failure_result(f"Confidence evaluation failed: {type(exc).__name__}.")

    def _evaluate(self, technical: Mapping[str, Any] | None, market: Mapping[str, Any] | None, option: Mapping[str, Any] | None, sentiment: Mapping[str, Any] | None, strategy: Mapping[str, Any] | None,smart_money: Mapping[str, Any] | None,risk=None,) -> dict[str, Any]:
        technical_data, market_data = self._mapping(technical), self._mapping(market)
        option_data, sentiment_data, strategy_data = self._mapping(option), self._mapping(sentiment), self._mapping(strategy) 
        smart_money_data = self._mapping(smart_money)
        risk_data = self._mapping(
        risk
        )
        signals = {"technical": self._technical_signal(technical_data), "market": self._market_signal(market_data), "option": self._option_signal(option_data), "sentiment": self._sentiment_signal(sentiment_data), "strategy": self._strategy_signal(strategy_data)}
        proposed = signals["strategy"].direction
        matrix = {name: bool(proposed in {"BULLISH", "BEARISH"} and signal.available and signal.direction == proposed) for name, signal in signals.items()}
        if proposed == "NEUTRAL":
            matrix["strategy"] = True
        agreement_percent = round(sum(matrix.values()) * 100.0 / len(matrix), 2)
        score = sum(self.config.agreement_points for agreed in matrix.values() if agreed)
        strengths: list[str] = []
        weaknesses: list[str] = []
        reasons: list[str] = []
        if all(matrix.values()):
            score = self._append_confirmation(True, self.config.all_agree_bonus, "All analysis engines agree with the strategy", score, strengths, reasons)
        elif proposed in {"BULLISH", "BEARISH"}:
            conflicts = [name for name, signal in signals.items() if signal.available and signal.direction not in {proposed, "NEUTRAL"}]
            if conflicts:
                score -= self.config.conflict_penalty
                weaknesses.append("Conflicting directional signals: " + ", ".join(conflicts))
                reasons.append("Confidence reduced because engines conflict with the strategy.")

        indicators = self._indicators(technical_data)
        adx, volume, volume_average = self._number(indicators, "ADX"), self._number(indicators, "VOLUME"), self._number(indicators, "VOLUME_EMA20")
        vix = self._number(indicators, "INDIA_VIX")
        price, vwap = self._number(indicators, "CURRENT_PRICE"), self._number(indicators, "VWAP")
        technical_direction = signals["technical"].direction
        market_direction = signals["market"].direction
        if technical_direction == proposed and market_direction == proposed and signals["technical"].strength >= 50 and signals["market"].strength >= 50:
            score = self._append_confirmation(True, self.config.strong_trend_bonus, "Technical and market trend strength align", score, strengths, reasons)
        if adx is None:
            weaknesses.append("ADX is unavailable")
        elif adx >= self.config.high_adx:
            score = self._append_confirmation(True, self.config.high_adx_bonus, "ADX confirms a strong trend", score, strengths, reasons)
        else:
            score -= self.config.weak_adx_penalty; weaknesses.append("ADX does not confirm trend strength"); reasons.append("Confidence reduced: ADX is weak.")
        if volume is None or volume_average is None or volume_average <= 0:
            weaknesses.append("Volume confirmation is unavailable")
        elif volume >= volume_average * self.config.strong_volume_ratio:
            score = self._append_confirmation(True, self.config.high_volume_bonus, "Volume confirms the move", score, strengths, reasons)
        else:
            score -= self.config.low_volume_penalty; weaknesses.append("Volume is below its reference level"); reasons.append("Confidence reduced: volume is low.")
        if price is not None and vwap is not None and ((proposed == "BULLISH" and price > vwap) or (proposed == "BEARISH" and price < vwap)):
            score = self._append_confirmation(True, self.config.vwap_bonus, "Price is confirmed by VWAP", score, strengths, reasons)
        if (proposed == "BULLISH" and self._truthy(indicators, "BREAKOUT")) or (proposed == "BEARISH" and self._truthy(indicators, "BREAKDOWN")):
            score = self._append_confirmation(True, self.config.breakout_bonus, "Breakout structure confirms the trade", score, strengths, reasons)
        if vix is not None:
            if vix >= self.config.extreme_vix:
                score -= self.config.extreme_vix_penalty; weaknesses.append("India VIX is extremely high"); reasons.append("Confidence reduced: extreme volatility.")
            elif vix >= self.config.high_vix:
                score -= self.config.high_vix_penalty; weaknesses.append("India VIX is elevated"); reasons.append("Confidence reduced: elevated volatility.")
        context = str(market_data.get("trend", "")).strip().upper()
        market_regime = str(
                    market_data.get(
                        "market_regime",
                        "UNKNOWN",
                    )
                ).upper()
        # -------------------------------------------------
        # Market Regime Weighting
        # -------------------------------------------------

        if market_regime == "TRENDING":

            score += 6

            strengths.append(
                "Trending Market Regime"
            )

        elif market_regime == "SIDEWAYS":

            score -= 8

            weaknesses.append(
                "Sideways Market Regime"
            )

        elif market_regime == "HIGH_VOLATILITY":

            score -= 5

            weaknesses.append(
                "High Volatility Regime"
            )
        if context in {"SIDEWAYS", "RANGE"}:
            score -= self.config.range_penalty; weaknesses.append("Market context is sideways or range-bound"); reasons.append("Confidence reduced: range-market conditions.")
        if not signals["option"].available:
            score -= self.config.missing_option_penalty; weaknesses.append("Option-chain confirmation is missing"); reasons.append("Confidence reduced: option-chain data is missing.")
        elif matrix["option"]:
            score = self._append_confirmation(True, self.config.option_confirmation_bonus, "PCR, OI, or option structure confirms direction", score, strengths, reasons)
        if not signals["sentiment"].available:
            score -= self.config.missing_sentiment_penalty; weaknesses.append("Sentiment confirmation is missing"); reasons.append("Confidence reduced: sentiment data is missing.")
        elif matrix["sentiment"] and signals["sentiment"].strength >= 50:
            score = self._append_confirmation(True, self.config.strong_sentiment_bonus, "Sentiment strongly confirms direction", score, strengths, reasons)
        if proposed not in {"BULLISH", "BEARISH"}:
            score = min(score, self.config.hold_confidence_cap)
            weaknesses.append("Strategy is HOLD; no actionable directional consensus")
            reasons.append("Confidence capped because strategy has no trade direction.")
        # -------------------------------------------------
        # Smart Money Confirmation
        # -------------------------------------------------

        bos = smart_money_data.get("bos")

        choch = smart_money_data.get("choch")

        liquidity = smart_money_data.get(
            "liquidity",
            {},
        )
        fair_value_gaps = smart_money_data.get(
            "fair_value_gaps",
            {},
        )
        
        bullish_ob = (
            smart_money_data.get(
                "order_blocks",
                {},
            ).get("bullish")
            is not None
        )

        bearish_ob = (
            smart_money_data.get(
                "order_blocks",
                {},
            ).get("bearish")
            is not None
        )

        if proposed == "BULLISH":

            if str(bos).upper() == "BULLISH":

                score += 8

                strengths.append(
                    "Bullish BOS confirmed"
                )

            if bullish_ob:

                score += 6

                strengths.append(
                    "Bullish Order Block"
                )
            if liquidity.get("bullish"):

                score += 5

                strengths.append(
                    "Bullish Liquidity Sweep"
                )
            if fair_value_gaps.get("bullish") is not None:

                score += 5

                strengths.append(
                    "Bullish Fair Value Gap"
                )

        elif proposed == "BEARISH":

            if str(bos).upper() == "BEARISH":

                score += 8

                strengths.append(
                    "Bearish BOS confirmed"
                )

            if bearish_ob:

                score += 6

                strengths.append(
                    "Bearish Order Block"
                )
            if liquidity.get("bearish"):

                score += 5

                strengths.append(
                    "Bearish Liquidity Sweep"
                )
            if fair_value_gaps.get("bearish") is not None:

                score += 5

                strengths.append(
                    "Bearish Fair Value Gap"
                )

        if choch:

            score += 4

            strengths.append(
                "CHOCH detected"
            )
        # -------------------------------------------------
        # Risk Quality Confirmation
        # -------------------------------------------------

        risk_reward = self._number(
            risk_data,
            "risk_reward",
            "RR",
        )

        if risk_reward is not None:

            if risk_reward >= 2.0:

                score += 6

                strengths.append(
                    "Excellent Risk/Reward"
                )

            elif risk_reward >= 1.5:

                score += 3

                strengths.append(
                    "Good Risk/Reward"
                )

            elif risk_reward < 1.0:

                score -= 8

                weaknesses.append(
                    "Poor Risk/Reward"
                )

                reasons.append(
                    "Confidence reduced: poor risk/reward."
                )
        # -------------------------------------------------
        # Adaptive Confidence Cap
        # -------------------------------------------------

        confidence_cap = 100.0

        if market_regime == "SIDEWAYS":

            confidence_cap = 85.0

        elif market_regime == "HIGH_VOLATILITY":

            confidence_cap = 80.0

        elif context in {"SIDEWAYS", "RANGE"}:

            confidence_cap = min(
                confidence_cap,
                85.0,
            )
        base_confidence = round(
            min(
                confidence_cap,
                max(0.0, score),
            ),
            2,
        )
        # -------------------------------------------------
        # Weakness Accumulation Penalty
        # -------------------------------------------------

        weakness_count = len(
            set(weaknesses)
        )

        if weakness_count >= 6:

            score -= 12

            reasons.append(
                "Confidence reduced: multiple risk factors detected."
            )

        elif weakness_count >= 4:

            score -= 6

            reasons.append(
                "Confidence reduced: several weaknesses remain."
            )

        # -------------------------------------------------
        # Diminishing Returns for Excessive Confirmations
        # -------------------------------------------------

        strength_count = len(
            set(strengths)
        )

        if strength_count >= 10:

            score -= 8

            reasons.append(
                "Confidence normalized due to excessive overlapping confirmations."
            )

        elif strength_count >= 8:

            score -= 5

        elif strength_count >= 6:

            score -= 2
        # -------------------------------------------------
        # Minimum Confirmation Requirement
        # -------------------------------------------------

        confirmation_count = len(
            set(strengths)
        )

        if proposed in {"BULLISH", "BEARISH"}:

            if confirmation_count < 4:

                score = min(
                    score,
                    60,
                )

                reasons.append(
                    "Confidence capped due to insufficient confirmations."
                )

            elif confirmation_count < 6:

                score = min(
                    score,
                    75,
                )

        confidence = adaptive_confidence_engine.adjust(
            base_confidence
        )
        return self._result(confidence, agreement_percent, matrix, strengths, weaknesses, reasons, proposed)

    def _result(self, confidence: float, agreement: float, matrix: dict[str, bool], strengths: list[str], weaknesses: list[str], reasons: list[str], direction: str | None) -> dict[str, Any]:
        grade = "A+" if confidence >= 90 else "A" if confidence >= 75 else "B" if confidence >= 60 else "C" if confidence >= 45 else "D"
        quality = "AVOID" if direction not in {"BULLISH", "BEARISH"} or confidence < 40 else "EXCELLENT" if confidence >= 85 else "GOOD" if confidence >= 70 else "AVERAGE" if confidence >= 55 else "POOR"
        signal = "BUY" if direction == "BULLISH" and quality != "AVOID" else "SELL" if direction == "BEARISH" and quality != "AVOID" else "HOLD"
        summary_parts = []

        if strengths:
            summary_parts.append(
                f"{len(strengths)} strengths"
            )

        if weaknesses:
            summary_parts.append(
                f"{len(weaknesses)} weaknesses"
            )

        summary_parts.append(
            f"Agreement: {agreement:.0f}%"
        )

        summary = " | ".join(
            summary_parts
        )
        return {"confidence": confidence, "confidence_summary": summary, "grade": grade, "trade_quality": quality, "agreement_percent": agreement, "agreement_matrix": matrix, "strengths": list(dict.fromkeys(strengths)), "weaknesses": list(dict.fromkeys(weaknesses)), "reasons": list(dict.fromkeys(reasons)), "signal": signal, "bull_score": confidence if direction == "BULLISH" else 0.0, "bear_score": confidence if direction == "BEARISH" else 0.0, "neutral_score": 100.0 - confidence, "reason": "; ".join(dict.fromkeys(reasons))}

    def _failure_result(self, reason: str) -> dict[str, Any]:
        return self._result(0.0, 0.0, {"technical": False, "market": False, "option": False, "sentiment": False, "strategy": False}, [], [reason], [reason], None)


def calculate_confidence(
    technical: Mapping[str, Any] | None = None,
    market: Mapping[str, Any] | None = None,
    option: Mapping[str, Any] | None = None,
    sentiment: Mapping[str, Any] | None = None,
    strategy: Mapping[str, Any] | None = None,
    smart_money=None,
    **_: Any,
) -> dict[str, Any]:
    """Compatibility entry point for the production confidence engine."""
    return ConfidenceEngine().evaluate(
        technical,
        market,
        option,
        sentiment,
        strategy,
        smart_money,
    )
