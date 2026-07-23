"""Central, snapshot-only evidence collection for master trade decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import math
from collections.abc import Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EvidenceConfig:
    """Source weights and thresholds used when aggregating supplied evidence."""

    technical_weight: float = 1.00
    market_weight: float = 1.00
    option_weight: float = 0.90
    sentiment_weight: float = 0.45
    strategy_weight: float = 1.10
    confidence_weight: float = 0.75
    regime_weight: float = 0.85
    validator_weight: float = 1.25
    timeframe_weight: float = 0.90
    trade_quality_weight: float = 1.10
    strong_confidence: float = 60.0
    critical_confidence: float = 80.0
    bias_threshold: float = 1.0


@dataclass(slots=True)
class EvidenceItem:
    direction: str
    source: str
    message: str
    weight: float
    severity: str
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceEngine:
    """Collect normalized directional evidence without recalculating analytics."""

    def __init__(self, config: EvidenceConfig | None = None) -> None:
        self.config = config or EvidenceConfig()

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
        if text in {"BULLISH", "BULL", "BUY", "LONG", "UP", "UPTREND", "TRENDING_BULL", "BREAKOUT", "GAP_UP_TREND_DAY"}: return "BULLISH"
        if text in {"BEARISH", "BEAR", "SELL", "SHORT", "DOWN", "DOWNTREND", "TRENDING_BEAR", "BREAKDOWN", "GAP_DOWN_TREND_DAY"}: return "BEARISH"
        if text in {"NEUTRAL", "SIDEWAYS", "RANGE", "RANGE_BOUND", "HOLD", "WAIT", "AVOID"}: return "NEUTRAL"
        return None

    def _score_item(self, source: str, data: Mapping[str, Any], weight: float, fallback_key: str | None = None, message: str | None = None) -> EvidenceItem | None:
        bull, bear = self._number(data, "bull_score", "bull"), self._number(data, "bear_score", "bear")
        if bull is not None and bear is not None and bull >= 0 and bear >= 0 and bull + bear > 0:
            delta = (bull - bear) * 100.0 / (bull + bear)
            direction = "NEUTRAL" if abs(delta) < 5.0 else "BULLISH" if delta > 0 else "BEARISH"
            return self._item(direction, source, message or f"{source.title()} directional score is {direction.lower()}.", weight, abs(delta))
        direction = self._direction(data.get(fallback_key)) if fallback_key else None
        if direction is not None:
            confidence = self._number(data, "confidence", "alignment_percent", "overall_score", "validation_score") or 50.0
            return self._item(direction, source, message or f"{source.title()} reports a {direction.lower()} state.", weight, confidence)
        return None

    def _item(self, direction: str, source: str, message: str, weight: float, confidence: float, severity: str | None = None) -> EvidenceItem:
        bounded = self._clamp(confidence)
        resolved_severity = severity or ("CRITICAL" if bounded >= self.config.critical_confidence and direction in {"BULLISH", "BEARISH"} else "STRONG" if bounded >= self.config.strong_confidence else "WEAK")
        return EvidenceItem(direction, source, message, round(weight, 3), resolved_severity, bounded)

    def collect(self, technical: Mapping[str, Any] | None = None, market: Mapping[str, Any] | None = None, option: Mapping[str, Any] | None = None, sentiment: Mapping[str, Any] | None = None, strategy: Mapping[str, Any] | None = None, confidence: Mapping[str, Any] | float | int | None = None, market_regime: Mapping[str, Any] | None = None, decision_validator: Mapping[str, Any] | None = None, multi_timeframe: Mapping[str, Any] | None = None, trade_quality: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Collect every available directional output and identify conflicts safely."""
        try:
            return self._collect(technical, market, option, sentiment, strategy, confidence, market_regime, decision_validator, multi_timeframe, trade_quality)
        except Exception as exc:
            logger.exception("Evidence collection failed")
            return self._failure_result(f"Evidence collection failed: {type(exc).__name__}.")

    def _collect(self, technical: Mapping[str, Any] | None, market: Mapping[str, Any] | None, option: Mapping[str, Any] | None, sentiment: Mapping[str, Any] | None, strategy: Mapping[str, Any] | None, confidence: Mapping[str, Any] | float | int | None, market_regime: Mapping[str, Any] | None, decision_validator: Mapping[str, Any] | None, multi_timeframe: Mapping[str, Any] | None, trade_quality: Mapping[str, Any] | None) -> dict[str, Any]:
        payloads = {"technical": self._mapping(technical), "market": self._mapping(market), "option": self._mapping(option), "sentiment": self._mapping(sentiment), "strategy": self._mapping(strategy), "market_regime": self._mapping(market_regime), "decision_validator": self._mapping(decision_validator), "multi_timeframe": self._mapping(multi_timeframe), "trade_quality": self._mapping(trade_quality)}
        weights = {"technical": self.config.technical_weight, "market": self.config.market_weight, "option": self.config.option_weight, "sentiment": self.config.sentiment_weight, "strategy": self.config.strategy_weight, "confidence": self.config.confidence_weight, "market_regime": self.config.regime_weight, "decision_validator": self.config.validator_weight, "multi_timeframe": self.config.timeframe_weight, "trade_quality": self.config.trade_quality_weight}
        items: list[EvidenceItem] = []
        missing: list[dict[str, str]] = []
        for source, payload in payloads.items():
            if not payload:
                missing.append({"source": source, "reason": f"{source.replace('_', ' ').title()} output is missing."})
        self._add_if(items, self._score_item("technical", payloads["technical"], weights["technical"], "trend"))
        self._add_categories(items, "technical", payloads["technical"], weights["technical"])
        self._add_if(items, self._score_item("market", payloads["market"], weights["market"], "trend"))
        self._add_categories(items, "market", payloads["market"], weights["market"])
        self._add_if(items, self._score_item("option", payloads["option"], weights["option"]))
        self._add_categories(items, "option", payloads["option"], weights["option"])
        self._add_if(items, self._score_item("sentiment", payloads["sentiment"], weights["sentiment"], "summary"))
        self._add_if(items, self._strategy_item(payloads["strategy"], weights["strategy"]))
        self._add_if(items, self._confidence_item(confidence, weights["confidence"]))
        self._add_if(items, self._score_item("market_regime", payloads["market_regime"], weights["market_regime"], "regime"))
        self._add_if(items, self._timeframe_item(payloads["multi_timeframe"], weights["multi_timeframe"]))
        self._add_validator_items(items, payloads["decision_validator"], weights["decision_validator"])
        self._add_quality_item(items, payloads["trade_quality"], weights["trade_quality"])
        for source, payload in payloads.items():
            if payload and not any(item.source == source for item in items) and source not in {"decision_validator", "trade_quality"}:
                missing.append({"source": source, "reason": f"{source.replace('_', ' ').title()} contains no usable directional evidence."})
        conflicts = self._conflicts(items)
        bullish = [item for item in items if item.direction == "BULLISH"]
        bearish = [item for item in items if item.direction == "BEARISH"]
        neutral = [item for item in items if item.direction == "NEUTRAL"]
        weighted = round(sum(item.weight * item.confidence / 100.0 for item in bullish) - sum(item.weight * item.confidence / 100.0 for item in bearish), 3)
        bias = "BULLISH" if weighted >= self.config.bias_threshold else "BEARISH" if weighted <= -self.config.bias_threshold else "NEUTRAL"
        reasons = [f"Collected {len(items)} evidence items from {len(payloads) - len([entry for entry in missing if 'output is missing' in entry['reason']])} available sources.", f"Weighted evidence score is {weighted:.3f}, producing a {bias.lower()} bias."]
        if conflicts: reasons.append(f"Detected {len(conflicts)} conflicting evidence relationships.")
        if missing: reasons.append(f"Detected {len(missing)} missing or unusable evidence entries.")
        return {"bullish_count": len(bullish), "bearish_count": len(bearish), "neutral_count": len(neutral), "conflict_count": len(conflicts), "overall_bias": bias, "bullish_evidence": [item.as_dict() for item in bullish], "bearish_evidence": [item.as_dict() for item in bearish], "neutral_evidence": [item.as_dict() for item in neutral], "conflicting_evidence": conflicts, "missing_evidence": missing, "weighted_score": weighted, "summary": f"{bias.title()} evidence bias with {len(conflicts)} conflicts and {len(missing)} missing evidence entries.", "reasons": reasons}

    @staticmethod
    def _add_if(items: list[EvidenceItem], item: EvidenceItem | None) -> None:
        if item is not None: items.append(item)

    def _add_categories(self, items: list[EvidenceItem], source: str, data: Mapping[str, Any], source_weight: float) -> None:
        categories = data.get("category_scores")
        if not isinstance(categories, Mapping): return
        for name, raw in categories.items():
            category = self._mapping(raw)
            item = self._score_item(f"{source}.{name}", category, source_weight * 0.5, message=f"{source.title()} {str(name).replace('_', ' ')} category is directional.")
            self._add_if(items, item)

    def _strategy_item(self, data: Mapping[str, Any], weight: float) -> EvidenceItem | None:
        direction = self._direction(data.get("signal", data.get("recommendation")))
        if direction is None: return None
        return self._item(direction, "strategy", f"Strategy proposes {direction.lower()} execution.", weight, 100.0, "CRITICAL")

    def _confidence_item(self, confidence: Mapping[str, Any] | float | int | None, weight: float) -> EvidenceItem | None:
        value = self._number(confidence, "confidence") if isinstance(confidence, Mapping) else self._coerce(confidence)
        if value is None: return None
        direction = "NEUTRAL"
        if isinstance(confidence, Mapping): direction = self._direction(confidence.get("signal", confidence.get("trend"))) or "NEUTRAL"
        return self._item(direction, "confidence", f"Confidence engine reports {self._clamp(value):.2f} confidence.", weight, value, "STRONG" if value >= self.config.strong_confidence else "WEAK")

    def _timeframe_item(self, data: Mapping[str, Any], weight: float) -> EvidenceItem | None:
        direction = self._direction(data.get("overall_trend"))
        alignment = self._number(data, "alignment_percent")
        if direction is None or alignment is None: return None
        return self._item(direction, "multi_timeframe", f"Multi-timeframe alignment is {self._clamp(alignment):.2f}%.", weight, alignment)

    def _add_validator_items(self, items: list[EvidenceItem], data: Mapping[str, Any], weight: float) -> None:
        if not data: return
        approved = data.get("approved")
        score = self._number(data, "validation_score") or 0.0
        if approved is True:
            items.append(self._item("NEUTRAL", "decision_validator", "Decision validator approved the proposed trade.", weight, score, "STRONG" if score >= self.config.strong_confidence else "WEAK"))
        elif approved is False:
            items.append(self._item("NEUTRAL", "decision_validator", "Decision validator rejected or cautioned the proposed trade.", weight, 100.0, "CRITICAL"))
        for failure in self._text_items(data.get("critical_failures")):
            items.append(self._item("NEUTRAL", "decision_validator", failure, weight, 100.0, "CRITICAL"))
        for warning in self._text_items(data.get("warnings")):
            items.append(self._item("NEUTRAL", "decision_validator", warning, weight * 0.5, 50.0, "WEAK"))

    def _add_quality_item(self, items: list[EvidenceItem], data: Mapping[str, Any], weight: float) -> None:
        if not data: return
        score = self._number(data, "overall_score") or 0.0
        should_trade = data.get("should_trade")
        direction = self._direction(data.get("recommendation", data.get("signal"))) or "NEUTRAL"
        message = "Trade-quality engine supports execution." if should_trade is True else "Trade-quality engine does not support execution."
        items.append(self._item(direction, "trade_quality", message, weight, score, "STRONG" if should_trade is True and score >= self.config.strong_confidence else "CRITICAL" if should_trade is False else "WEAK"))

    def _conflicts(self, items: list[EvidenceItem]) -> list[dict[str, Any]]:
        directional = [item for item in items if item.direction in {"BULLISH", "BEARISH"}]
        conflicts: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for index, left in enumerate(directional):
            for right in directional[index + 1:]:
                if left.direction == right.direction: continue
                pair = tuple(sorted((left.source, right.source)))
                if pair in seen: continue
                seen.add(pair)
                conflicts.append({"sources": list(pair), "directions": {left.source: left.direction, right.source: right.direction}, "severity": "CRITICAL" if left.severity == "CRITICAL" or right.severity == "CRITICAL" else "STRONG", "message": f"{left.source} and {right.source} provide opposing directional evidence."})
        return conflicts

    @staticmethod
    def _text_items(value: Any) -> list[str]:
        return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []

    @staticmethod
    def _coerce(value: Any) -> float | None:
        try:
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _failure_result(reason: str) -> dict[str, Any]:
        return {"bullish_count": 0, "bearish_count": 0, "neutral_count": 0, "conflict_count": 0, "overall_bias": "NEUTRAL", "bullish_evidence": [], "bearish_evidence": [], "neutral_evidence": [], "conflicting_evidence": [], "missing_evidence": [{"source": "evidence_engine", "reason": reason}], "weighted_score": 0.0, "summary": "Evidence collection failed.", "reasons": [reason]}


def collect_evidence(technical: Mapping[str, Any] | None = None, market: Mapping[str, Any] | None = None, option: Mapping[str, Any] | None = None, sentiment: Mapping[str, Any] | None = None, strategy: Mapping[str, Any] | None = None, confidence: Mapping[str, Any] | float | int | None = None, market_regime: Mapping[str, Any] | None = None, decision_validator: Mapping[str, Any] | None = None, multi_timeframe: Mapping[str, Any] | None = None, trade_quality: Mapping[str, Any] | None = None, config: EvidenceConfig | None = None) -> dict[str, Any]:
    """Convenience entry point for the central evidence layer."""
    return EvidenceEngine(config).collect(technical, market, option, sentiment, strategy, confidence, market_regime, decision_validator, multi_timeframe, trade_quality)
