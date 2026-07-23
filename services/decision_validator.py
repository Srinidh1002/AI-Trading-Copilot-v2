"""Final, snapshot-only trade validation gate.

The validator is intentionally downstream of analysis.  It reads existing
engine outputs, detects contradictions and data-quality failures, and never
recalculates indicators or changes a proposed trading direction.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DecisionValidatorConfig:
    minimum_confidence: float = 60.0
    caution_confidence: float = 50.0
    minimum_adx: float = 25.0
    minimum_volume_ratio: float = 1.0
    elevated_vix: float = 20.0
    extreme_vix: float = 28.0
    strong_directional_strength: float = 50.0
    rejection_penalty: float = 30.0
    warning_penalty: float = 10.0
    missing_data_penalty: float = 20.0


@dataclass(slots=True)
class DirectionalEvidence:
    direction: str | None = None
    strength: float = 0.0
    available: bool = False


class DecisionValidator:
    """Validate a proposed strategy using completed analysis-engine results."""

    def __init__(self, config: DecisionValidatorConfig | None = None) -> None:
        self.config = config or DecisionValidatorConfig()

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _number(data: Mapping[str, Any], *names: str) -> float | None:
        for name in names:
            try:
                value = float(data.get(name))
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                return value
        return None

    @staticmethod
    def _truthy(data: Mapping[str, Any], name: str) -> bool:
        value = data.get(name, False)
        return value is True or str(value).strip().upper() in {"TRUE", "YES", "1", "BULLISH"}

    @staticmethod
    def _direction(value: Any) -> str | None:
        text = str(value or "").strip().upper()
        if text in {"BUY", "BULL", "BULLISH", "LONG", "UP", "UPTREND"}:
            return "BULLISH"
        if text in {"SELL", "BEAR", "BEARISH", "SHORT", "DOWN", "DOWNTREND"}:
            return "BEARISH"
        if text in {"HOLD", "WAIT", "NEUTRAL", "SIDEWAYS", "RANGE"}:
            return "NEUTRAL"
        return None

    def _evidence(self, data: Mapping[str, Any], direction_key: str | None = None) -> DirectionalEvidence:
        bull = self._number(data, "bull_score", "bull")
        bear = self._number(data, "bear_score", "bear")
        if bull is not None and bear is not None and bull >= 0 and bear >= 0 and bull + bear > 0:
            delta = (bull - bear) * 100.0 / (bull + bear)
            direction = "NEUTRAL" if abs(delta) < 5.0 else "BULLISH" if delta > 0 else "BEARISH"
            return DirectionalEvidence(direction, round(abs(delta), 2), True)
        if direction_key:
            direction = self._direction(data.get(direction_key))
            if direction is not None:
                return DirectionalEvidence(direction, 50.0, True)
        return DirectionalEvidence()

    @staticmethod
    def _indicators(technical: Mapping[str, Any]) -> Mapping[str, Any]:
        indicators = technical.get("indicators")
        return indicators if isinstance(indicators, Mapping) else technical

    def _regime_supports(self, regime: str, direction: str) -> bool:
        if direction == "BULLISH":
            return regime in {"TRENDING_BULL", "BREAKOUT", "GAP_UP_TREND_DAY", "PULLBACK_TREND"}
        if direction == "BEARISH":
            return regime in {"TRENDING_BEAR", "BREAKDOWN", "GAP_DOWN_TREND_DAY", "PULLBACK_TREND"}
        return False

    @staticmethod
    def _strategy_kind(strategy: Mapping[str, Any]) -> str:
        text = " ".join(str(strategy.get(key, "")) for key in ("strategy", "strategy_name", "name", "setup", "signal")).upper()
        if "BREAKOUT" in text or "BREAKDOWN" in text:
            return "BREAKOUT"
        if "TREND" in text or "PULLBACK" in text:
            return "TREND"
        return "DIRECTIONAL"

    def validate(
        self,
        technical: Mapping[str, Any] | None = None,
        market: Mapping[str, Any] | None = None,
        option: Mapping[str, Any] | None = None,
        sentiment: Mapping[str, Any] | None = None,
        strategy: Mapping[str, Any] | None = None,
        confidence: Mapping[str, Any] | float | int | None = None,
        market_regime: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return an approval decision; all malformed input fails closed."""
        try:
            return self._validate(technical, market, option, sentiment, strategy, confidence, market_regime)
        except Exception as exc:
            logger.exception("Decision validation failed")
            return self._failure_result(f"Decision validation failed: {type(exc).__name__}.")

    def _validate(self, technical: Mapping[str, Any] | None, market: Mapping[str, Any] | None, option: Mapping[str, Any] | None, sentiment: Mapping[str, Any] | None, strategy: Mapping[str, Any] | None, confidence: Mapping[str, Any] | float | int | None, market_regime: Mapping[str, Any] | None) -> dict[str, Any]:
        technical_data, market_data = self._mapping(technical), self._mapping(market)
        option_data, sentiment_data, strategy_data, regime_data = self._mapping(option), self._mapping(sentiment), self._mapping(strategy), self._mapping(market_regime)
        confidence_value = self._number(confidence, "confidence") if isinstance(confidence, Mapping) else self._coerce_number(confidence)
        critical: list[str] = []
        warnings: list[str] = []
        positives: list[str] = []
        reasons: list[str] = []
        score = 100.0
        required = {"technical": technical_data, "market": market_data, "strategy": strategy_data, "market_regime": regime_data}
        for name, payload in required.items():
            if not payload:
                critical.append(f"Missing critical {name} output")
                reasons.append(f"Trade rejected: {name} output is required.")
                score -= self.config.missing_data_penalty
        if confidence_value is None:
            critical.append("Missing critical confidence output")
            reasons.append("Trade rejected: confidence output is required.")
            score -= self.config.missing_data_penalty
        if not option_data:
            warnings.append("Option-chain output is missing")
            reasons.append("Caution: option confirmation is unavailable.")
            score -= self.config.warning_penalty
        if not sentiment_data:
            warnings.append("Sentiment output is missing")
            reasons.append("Caution: sentiment confirmation is unavailable.")
            score -= self.config.warning_penalty / 2.0

        proposed = self._direction(strategy_data.get("signal", strategy_data.get("recommendation")))
        if proposed not in {"BULLISH", "BEARISH"}:
            critical.append("Strategy does not propose an actionable BUY or SELL trade")
            reasons.append("Trade rejected: strategy is HOLD, neutral, or unavailable.")
            score -= self.config.rejection_penalty
        technical_evidence = self._evidence(technical_data)
        market_evidence = self._evidence(market_data, "trend")
        option_evidence = self._evidence(option_data)
        sentiment_evidence = self._evidence(sentiment_data, "summary")
        if confidence_value is not None:
            if confidence_value < self.config.caution_confidence:
                critical.append(f"Confidence {confidence_value:.2f} is below the minimum threshold")
                reasons.append("Trade rejected: confidence is below the configured minimum.")
                score -= self.config.rejection_penalty
            elif confidence_value < self.config.minimum_confidence:
                warnings.append(f"Confidence {confidence_value:.2f} is below the approval threshold")
                reasons.append("Caution: confidence is below the approval threshold.")
                score -= self.config.warning_penalty
            else:
                positives.append("Confidence meets the approval threshold")
        if self._strong_conflict(technical_evidence, market_evidence):
            critical.append("Technical and market engines strongly disagree")
            reasons.append("Trade rejected: technical direction strongly conflicts with market direction.")
            score -= self.config.rejection_penalty
        elif proposed and technical_evidence.direction == proposed and market_evidence.direction == proposed:
            positives.append("Technical and market direction agree with the strategy")
        if self._strong_conflict(option_evidence, DirectionalEvidence(proposed, 100.0, proposed is not None)):
            critical.append("Option flow strongly disagrees with the strategy")
            reasons.append("Trade rejected: option-chain direction conflicts with the proposed trade.")
            score -= self.config.rejection_penalty
        elif option_evidence.available and option_evidence.direction == proposed:
            positives.append("Option chain agrees with the strategy")
        regime = str(regime_data.get("regime", "")).strip().upper()
        strategy_kind = self._strategy_kind(strategy_data)
        if regime in {"TRENDING_BULL", "BREAKOUT", "GAP_UP_TREND_DAY"} and proposed == "BEARISH" or regime in {"TRENDING_BEAR", "BREAKDOWN", "GAP_DOWN_TREND_DAY"} and proposed == "BULLISH":
            critical.append(f"Market regime {regime or 'UNKNOWN'} contradicts the strategy")
            reasons.append("Trade rejected: market regime contradicts strategy direction.")
            score -= self.config.rejection_penalty
        elif regime in {"SIDEWAYS", "RANGE_BOUND"} and strategy_kind == "BREAKOUT":
            critical.append("Sideways/range regime is incompatible with a breakout strategy")
            reasons.append("Trade rejected: breakout strategy lacks a directional regime.")
            score -= self.config.rejection_penalty
        elif regime == "RANGE_BOUND" and strategy_kind == "TREND":
            critical.append("Range-bound regime is incompatible with a trend strategy")
            reasons.append("Trade rejected: trend strategy conflicts with range-bound regime.")
            score -= self.config.rejection_penalty
        elif self._regime_supports(regime, proposed or ""):
            positives.append("Market regime supports the strategy")
        else:
            warnings.append(f"Market regime {regime or 'UNKNOWN'} provides limited strategy support")
            reasons.append("Caution: market regime does not explicitly support the trade.")
            score -= self.config.warning_penalty

        indicators = self._indicators(technical_data)
        adx, volume, average_volume, vix = self._number(indicators, "ADX"), self._number(indicators, "VOLUME"), self._number(indicators, "VOLUME_EMA20"), self._number(indicators, "INDIA_VIX")
        price, vwap = self._number(indicators, "CURRENT_PRICE"), self._number(indicators, "VWAP")
        if adx is None:
            warnings.append("ADX confirmation is missing")
            score -= self.config.warning_penalty
        elif adx < self.config.minimum_adx and strategy_kind in {"TREND", "DIRECTIONAL"}:
            warnings.append("ADX does not confirm a strong trend")
            reasons.append("Caution: ADX is weak for the proposed directional trade.")
            score -= self.config.warning_penalty
        else:
            positives.append("ADX confirms trend strength")
        if volume is None or average_volume is None or average_volume <= 0:
            warnings.append("Volume confirmation is missing")
            score -= self.config.warning_penalty
        elif volume < average_volume * self.config.minimum_volume_ratio:
            warnings.append("Volume is below its confirmation threshold")
            reasons.append("Caution: volume does not confirm the move.")
            score -= self.config.warning_penalty
        else:
            positives.append("Volume confirms participation")
        if vix is not None and vix >= self.config.elevated_vix and (confidence_value is None or confidence_value < self.config.minimum_confidence):
            severity = self.config.rejection_penalty if vix >= self.config.extreme_vix else self.config.warning_penalty
            (critical if vix >= self.config.extreme_vix else warnings).append("High India VIX with insufficient confidence")
            reasons.append("Trade quality reduced: volatility is high while confidence is weak.")
            score -= severity
        if price is not None and vwap is not None and ((proposed == "BULLISH" and price > vwap) or (proposed == "BEARISH" and price < vwap)):
            positives.append("VWAP confirms strategy direction")
        elif price is not None and vwap is not None:
            warnings.append("VWAP contradicts strategy direction")
            score -= self.config.warning_penalty
        if technical_evidence.available and market_evidence.available and option_evidence.available and sentiment_evidence.available:
            directions = {item.direction for item in (technical_evidence, market_evidence, option_evidence, sentiment_evidence) if item.direction in {"BULLISH", "BEARISH"}}
            if len(directions) > 1:
                warnings.append("BUY and SELL evidence conflicts across engines")
                reasons.append("Caution: directional evidence is conflicted.")
                score -= self.config.warning_penalty
        validation_score = round(min(100.0, max(0.0, score)), 2)
        approved = not critical and not warnings and validation_score >= self.config.minimum_confidence
        status = "APPROVED" if approved else "REJECTED" if critical or validation_score < self.config.caution_confidence else "CAUTION"
        if approved:
            reasons.append("All required validations passed without major conflicts.")
        return {"approved": approved, "validation_score": validation_score, "status": status, "critical_failures": list(dict.fromkeys(critical)), "warnings": list(dict.fromkeys(warnings)), "positive_checks": list(dict.fromkeys(positives)), "reasons": list(dict.fromkeys(reasons))}

    @staticmethod
    def _coerce_number(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _strong_conflict(self, first: DirectionalEvidence, second: DirectionalEvidence) -> bool:
        return first.available and second.available and first.direction in {"BULLISH", "BEARISH"} and second.direction in {"BULLISH", "BEARISH"} and first.direction != second.direction and first.strength >= self.config.strong_directional_strength and second.strength >= self.config.strong_directional_strength

    def _failure_result(self, reason: str) -> dict[str, Any]:
        return {"approved": False, "validation_score": 0.0, "status": "REJECTED", "critical_failures": [reason], "warnings": [], "positive_checks": [], "reasons": [reason]}


def validate_decision(
    technical: Mapping[str, Any] | None = None,
    market: Mapping[str, Any] | None = None,
    option: Mapping[str, Any] | None = None,
    sentiment: Mapping[str, Any] | None = None,
    strategy: Mapping[str, Any] | None = None,
    confidence: Mapping[str, Any] | float | int | None = None,
    market_regime: Mapping[str, Any] | None = None,
    config: DecisionValidatorConfig | None = None,
) -> dict[str, Any]:
    """Convenience entry point for the final decision-validation gate."""
    return DecisionValidator(config).validate(technical, market, option, sentiment, strategy, confidence, market_regime)
