"""Institutional final-decision orchestration over completed engine outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MasterDecisionConfig:
    """Configurable hard gates for final recommendation authority."""

    minimum_confidence: float = 60.0
    minimum_trade_quality: float = 70.0
    minimum_validation_score: float = 60.0
    minimum_timeframe_alignment: float = 70.0
    minimum_evidence_items: int = 4
    maximum_conflicts: int = 0
    reject_high_risk: bool = True
    mandatory_inputs: tuple[str, ...] = (
        "technical", "market", "option", "sentiment", "strategy", "confidence",
        "market_regime", "decision_validator", "multi_timeframe", "trade_quality", "evidence",
    )
    bullish_regimes: frozenset[str] = frozenset({"TRENDING_BULL", "BREAKOUT", "GAP_UP_TREND_DAY", "PULLBACK_TREND"})
    bearish_regimes: frozenset[str] = frozenset({"TRENDING_BEAR", "BREAKDOWN", "GAP_DOWN_TREND_DAY", "PULLBACK_TREND"})


@dataclass(slots=True)
class DirectionalState:
    direction: str | None = None
    strength: float = 0.0
    available: bool = False


class MasterDecisionEngine:
    """Produce one fail-closed trading decision from existing engine outputs."""

    def __init__(self, config: MasterDecisionConfig | None = None, clock: Callable[[], datetime] | None = None) -> None:
        self.config = config or MasterDecisionConfig()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

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
            if math.isfinite(value): return value
        return None

    @staticmethod
    def _coerce_number(value: Any) -> float | None:
        try:
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _direction(value: Any) -> str | None:
        text = str(value or "").strip().upper()
        if text in {"BUY", "BULL", "BULLISH", "LONG", "UP", "UPTREND", "TRENDING_BULL", "BREAKOUT", "GAP_UP_TREND_DAY"}: return "BULLISH"
        if text in {"SELL", "BEAR", "BEARISH", "SHORT", "DOWN", "DOWNTREND", "TRENDING_BEAR", "BREAKDOWN", "GAP_DOWN_TREND_DAY"}: return "BEARISH"
        if text in {"HOLD", "WAIT", "NEUTRAL", "SIDEWAYS", "RANGE", "RANGE_BOUND", "AVOID"}: return "NEUTRAL"
        return None

    def _state(self, payload: Mapping[str, Any], fallback: str | None = None) -> DirectionalState:
        bull, bear = self._number(payload, "bull_score", "bull"), self._number(payload, "bear_score", "bear")
        if bull is not None and bear is not None and bull + bear > 0:
            delta = (bull - bear) * 100.0 / (bull + bear)
            return DirectionalState("NEUTRAL" if abs(delta) < 5 else "BULLISH" if delta > 0 else "BEARISH", abs(delta), True)
        direction = self._direction(payload.get(fallback)) if fallback else None
        return DirectionalState(direction, 50.0 if direction else 0.0, direction is not None)

    def decide(self, technical: Mapping[str, Any] | None = None, market: Mapping[str, Any] | None = None, option: Mapping[str, Any] | None = None, sentiment: Mapping[str, Any] | None = None, strategy: Mapping[str, Any] | None = None, confidence: Mapping[str, Any] | float | int | None = None, market_regime: Mapping[str, Any] | None = None, decision_validator: Mapping[str, Any] | None = None, multi_timeframe: Mapping[str, Any] | None = None, trade_quality: Mapping[str, Any] | None = None, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Run validation, conflict detection, recommendation, and packaging safely."""
        try:
            return self._decide(technical, market, option, sentiment, strategy, confidence, market_regime, decision_validator, multi_timeframe, trade_quality, evidence)
        except Exception as exc:
            logger.exception("Master decision evaluation failed")
            return self._failure_result(f"Master decision evaluation failed: {type(exc).__name__}.")

    def _decide(self, technical: Mapping[str, Any] | None, market: Mapping[str, Any] | None, option: Mapping[str, Any] | None, sentiment: Mapping[str, Any] | None, strategy: Mapping[str, Any] | None, confidence: Mapping[str, Any] | float | int | None, market_regime: Mapping[str, Any] | None, decision_validator: Mapping[str, Any] | None, multi_timeframe: Mapping[str, Any] | None, trade_quality: Mapping[str, Any] | None, evidence: Mapping[str, Any] | None) -> dict[str, Any]:
        inputs = {"technical": self._mapping(technical), "market": self._mapping(market), "option": self._mapping(option), "sentiment": self._mapping(sentiment), "strategy": self._mapping(strategy), "market_regime": self._mapping(market_regime), "decision_validator": self._mapping(decision_validator), "multi_timeframe": self._mapping(multi_timeframe), "trade_quality": self._mapping(trade_quality), "evidence": self._mapping(evidence)}
        critical, warnings, strengths, weaknesses = self._validate_inputs(inputs, confidence)
        proposed_action = str(inputs["strategy"].get("signal", inputs["strategy"].get("recommendation", ""))).strip().upper()
        proposed = self._direction(proposed_action)
        confidence_value = self._confidence_value(confidence)
        validator, quality, mtf, evidence_data, regime = inputs["decision_validator"], inputs["trade_quality"], inputs["multi_timeframe"], inputs["evidence"], inputs["market_regime"]
        validation_score, quality_score = self._number(validator, "validation_score"), self._number(quality, "overall_score")
        alignment, conflict_count = self._number(mtf, "alignment_percent"), self._number(evidence_data, "conflict_count")
        conflict_count = int(conflict_count or 0)
        states = {"technical": self._state(inputs["technical"], "trend"), "market": self._state(inputs["market"], "trend"), "option": self._state(inputs["option"]), "sentiment": self._state(inputs["sentiment"], "summary"), "timeframe": self._state(mtf, "overall_trend"), "evidence": self._state(evidence_data, "overall_bias")}
        self._apply_gates(proposed, confidence_value, validator, quality, validation_score, quality_score, alignment, conflict_count, regime, evidence_data, states, critical, warnings, strengths, weaknesses)
        final_decision, entry_allowed = self._recommend(proposed, proposed_action, critical, warnings, states, strengths)
        decision_score = self._decision_score(confidence_value, validation_score, quality_score, alignment, final_decision)
        approval_status = "REJECTED" if critical or final_decision == "NO_TRADE" else "CAUTION" if warnings or final_decision == "HOLD" else "APPROVED"
        priority = 1 if entry_allowed and decision_score >= 80 else 2 if entry_allowed else 3 if final_decision == "HOLD" else 4
        trade_grade = str(quality.get("grade", ""))
        trade_class = str(quality.get("trade_class", ""))
        summary = self._summary(final_decision, approval_status, decision_score, critical, warnings, proposed)
        return {"final_decision": final_decision, "decision_score": decision_score, "overall_confidence": round(confidence_value or 0.0, 2), "trade_grade": trade_grade, "trade_class": trade_class, "overall_market_bias": states["evidence"].direction or "NEUTRAL", "approval_status": approval_status, "entry_allowed": entry_allowed, "priority": priority, "strengths": self._unique(strengths), "weaknesses": self._unique(weaknesses), "critical_reasons": self._unique(critical), "warnings": self._unique(warnings), "summary": summary, "timestamp": self._timestamp(), "metadata": {"strategy_direction": proposed or "UNKNOWN", "validator_status": str(validator.get("status", "UNKNOWN")), "market_regime": str(regime.get("regime", "UNKNOWN")), "timeframe_alignment": alignment, "evidence_conflicts": conflict_count, "input_sources": {name: bool(payload) for name, payload in inputs.items()}}}

    def _validate_inputs(self, inputs: Mapping[str, Mapping[str, Any]], confidence: Any) -> tuple[list[str], list[str], list[str], list[str]]:
        critical: list[str] = []
        warnings: list[str] = []
        strengths: list[str] = []
        weaknesses: list[str] = []
        for name in self.config.mandatory_inputs:
            if name == "confidence":
                continue
            if not inputs.get(name):
                critical.append(f"Missing mandatory {name.replace('_', ' ')} output.")
                weaknesses.append(f"{name.replace('_', ' ').title()} is unavailable.")
        if self._confidence_value(confidence) is None:
            critical.append("Missing mandatory confidence output.")
            weaknesses.append("Confidence is unavailable.")
        return critical, warnings, strengths, weaknesses

    def _apply_gates(self, proposed: str | None, confidence: float | None, validator: Mapping[str, Any], quality: Mapping[str, Any], validation_score: float | None, quality_score: float | None, alignment: float | None, conflict_count: int, regime: Mapping[str, Any], evidence: Mapping[str, Any], states: Mapping[str, DirectionalState], critical: list[str], warnings: list[str], strengths: list[str], weaknesses: list[str]) -> None:
        if proposed not in {"BULLISH", "BEARISH"}:
            warnings.append("Strategy has no actionable BUY or SELL direction.")
            return
        if confidence is None or confidence < self.config.minimum_confidence:
            critical.append("Confidence is below the configured decision threshold.")
        else: strengths.append("Confidence meets the decision threshold.")
        if validator.get("approved") is not True or str(validator.get("status", "")).upper() != "APPROVED":
            critical.append("Decision validator has not approved the trade.")
        elif validation_score is not None and validation_score >= self.config.minimum_validation_score:
            strengths.append("Decision validator approved the trade.")
        else: critical.append("Decision-validator score is below the configured threshold.")
        if quality.get("should_trade") is not True or quality_score is None or quality_score < self.config.minimum_trade_quality:
            critical.append("Trade quality does not meet the configured threshold.")
        else: strengths.append("Trade quality meets the configured threshold.")
        if alignment is None or alignment < self.config.minimum_timeframe_alignment:
            critical.append("Multi-timeframe alignment is below the configured threshold.")
        elif states["timeframe"].direction != proposed:
            critical.append("Multi-timeframe direction contradicts the strategy.")
        else: strengths.append("Multi-timeframe direction and alignment support the trade.")
        evidence_count = sum(int(self._number(evidence, name) or 0) for name in ("bullish_count", "bearish_count", "neutral_count"))
        if evidence_count < self.config.minimum_evidence_items:
            critical.append("Insufficient collected evidence for a final decision.")
        if conflict_count > self.config.maximum_conflicts:
            critical.append("Evidence contains more directional conflicts than permitted.")
        if states["evidence"].direction != proposed:
            critical.append("Overall evidence bias does not support the strategy.")
        else: strengths.append("Overall evidence bias supports the strategy.")
        regime_name = str(regime.get("regime", "")).upper()
        supported = self.config.bullish_regimes if proposed == "BULLISH" else self.config.bearish_regimes
        if regime_name not in supported:
            critical.append("Market regime is unsuitable for the proposed strategy direction.")
        else: strengths.append("Market regime supports the strategy direction.")
        for name in ("technical", "market", "option"):
            state = states[name]
            if not state.available:
                critical.append(f"{name.title()} directional evidence is unavailable.")
            elif state.direction != proposed:
                critical.append(f"{name.title()} direction contradicts the strategy.")
            else: strengths.append(f"{name.title()} direction supports the strategy.")
        if states["sentiment"].available and states["sentiment"].direction not in {proposed, "NEUTRAL"}:
            warnings.append("Sentiment direction contradicts the strategy.")
        risk = str(quality.get("risk_level", "")).upper()
        if self.config.reject_high_risk and risk == "HIGH":
            critical.append("Trade-quality engine reports high risk.")
        for reason in self._text_list(validator.get("critical_failures")):
            critical.append(f"Validator critical failure: {reason}")
        for warning in self._text_list(validator.get("warnings")):
            warnings.append(f"Validator warning: {warning}")
        weaknesses.extend(self._text_list(quality.get("weaknesses")))

    def _recommend(self, proposed: str | None, proposed_action: str, critical: list[str], warnings: list[str], states: Mapping[str, DirectionalState], strengths: list[str]) -> tuple[str, bool]:
        if critical: return "NO_TRADE", False
        if proposed not in {"BULLISH", "BEARISH"}:
            return "HOLD", False
        if warnings: return "HOLD", False
        strengths.append("All final safety gates passed without warnings.")
        return ("BUY" if proposed == "BULLISH" else "SELL"), True

    @staticmethod
    def _decision_score(confidence: float | None, validation: float | None, quality: float | None, alignment: float | None, decision: str) -> float:
        values = [value for value in (confidence, validation, quality, alignment) if value is not None]
        if decision in {"NO_TRADE", "HOLD"} or not values: return 0.0
        return round(min(100.0, max(0.0, min(values))), 2)

    @staticmethod
    def _summary(decision: str, status: str, score: float, critical: list[str], warnings: list[str], proposed: str | None) -> str:
        if decision == "NO_TRADE": return f"NO_TRADE: {len(critical)} critical gate(s) prevented {proposed or 'unknown'} execution."
        if decision == "HOLD": return f"HOLD: final execution is deferred because {len(warnings)} warning(s) remain."
        return f"{decision} APPROVED: all safety gates passed with a conservative decision score of {score:.2f}."

    def _confidence_value(self, confidence: Mapping[str, Any] | float | int | None) -> float | None:
        return self._number(confidence, "confidence") if isinstance(confidence, Mapping) else self._coerce_number(confidence)

    @staticmethod
    def _text_list(value: Any) -> list[str]:
        return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []

    def _timestamp(self) -> str:
        timestamp = self._clock()
        return timestamp.astimezone(timezone.utc).isoformat() if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc).isoformat()

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value for value in values if value))

    def _failure_result(self, reason: str) -> dict[str, Any]:
        return {"final_decision": "NO_TRADE", "decision_score": 0.0, "overall_confidence": 0.0, "trade_grade": "", "trade_class": "", "overall_market_bias": "NEUTRAL", "approval_status": "REJECTED", "entry_allowed": False, "priority": 4, "strengths": [], "weaknesses": [reason], "critical_reasons": [reason], "warnings": [], "summary": "NO_TRADE: master decision engine failed closed.", "timestamp": self._timestamp(), "metadata": {}}


def make_master_decision(technical: Mapping[str, Any] | None = None, market: Mapping[str, Any] | None = None, option: Mapping[str, Any] | None = None, sentiment: Mapping[str, Any] | None = None, strategy: Mapping[str, Any] | None = None, confidence: Mapping[str, Any] | float | int | None = None, market_regime: Mapping[str, Any] | None = None, decision_validator: Mapping[str, Any] | None = None, multi_timeframe: Mapping[str, Any] | None = None, trade_quality: Mapping[str, Any] | None = None, evidence: Mapping[str, Any] | None = None, config: MasterDecisionConfig | None = None) -> dict[str, Any]:
    """Convenience API for a one-shot master decision."""
    return MasterDecisionEngine(config).decide(technical, market, option, sentiment, strategy, confidence, market_regime, decision_validator, multi_timeframe, trade_quality, evidence)
