"""
Decision Pipeline - 9 Gate System
PDF Section 3 - Fundamental Decision Hierarchy
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class GateStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCK = "BLOCK"


class DecisionAction(Enum):
    BUY_CALL = "BUY_CALL"
    BUY_PUT = "BUY_PUT"
    NO_TRADE = "NO_TRADE"
    WAIT = "WAIT"


@dataclass
class GateResult:
    gate_name: str
    status: GateStatus
    score: float = 0.0
    reason: str = ""
    details: Dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    market: str
    action: DecisionAction
    confidence: float
    composite_score: float
    gate_results: List[GateResult]
    reasons: List[str]
    technical_score: float = 0.0
    options_score: float = 0.0
    regime_score: float = 0.0
    global_score: float = 0.0
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target1: Optional[float] = None
    target2: Optional[float] = None
    target3: Optional[float] = None
    option_contract: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None


class DecisionPipeline:
    """Complete 9-Gate Decision Pipeline."""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.min_confidence = self.config.get("min_confidence", 40)
        self.min_risk_reward = self.config.get("min_risk_reward", 1.0)
        self.min_technical_score = self.config.get("min_technical_score", 40)
        self.min_options_score = self.config.get("min_options_score", 40)
    
    def run(self, market: str, data: Dict) -> PipelineResult:
        """Run the complete decision pipeline."""
        gate_results = []
        reasons = []
        confidence_multiplier = 1.0
        
        # GATE 1: DATA_VALIDITY
        gate_result = self._gate_data_validity(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Data validity failed", gate_results)
        reasons.append(gate_result.reason)
        
        # GATE 2: MARKET_SESSION_VALIDITY
        gate_result = self._gate_market_session(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Market session invalid", gate_results)
        reasons.append(gate_result.reason)
        
        # GATE 2.5: PRE-MARKET INTELLIGENCE
        try:
            from services.analysis.pre_market_intelligence import analyze_pre_market
            pre_market = analyze_pre_market(data)
            gate_results.append(GateResult(
                gate_name="PRE_MARKET",
                status=GateStatus.PASS if not pre_market.get("blockers") else GateStatus.FAIL,
                score=pre_market.get("overall_score", 50),
                reason=f"Pre-market: {pre_market.get('overall_score', 50):.1f}"
            ))
            if pre_market.get("blockers"):
                return self._no_trade_result(market, f"Pre-market blockers: {pre_market['blockers']}", gate_results)
            reasons.extend(pre_market.get("reasons", []))
        except ImportError as e:
            self.logger.warning(f"Pre-market intelligence not available: {e}")
            gate_results.append(GateResult(
                gate_name="PRE_MARKET",
                status=GateStatus.PASS,
                score=50,
                reason="Pre-market intelligence skipped (not available)"
            ))
        
        # GATE 3: MACRO / GLOBAL ENVIRONMENT
        global_score, gate_result = self._gate_global_environment(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Global environment unfavorable", gate_results)
        reasons.append(gate_result.reason)
        
        # GATE 4: MARKET REGIME
        regime_score, gate_result = self._gate_market_regime(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Regime unfavorable", gate_results)
        reasons.append(gate_result.reason)
        
        # GATE 5: MARKET COMPARISON (Simplified)
        try:
            nifty_score = data.get("nifty_score", 50)
            sensex_score = data.get("sensex_score", 50)
            
            if nifty_score > sensex_score and nifty_score >= 60:
                selected_market = "NIFTY"
                confidence = nifty_score
            elif sensex_score > nifty_score and sensex_score >= 60:
                selected_market = "SENSEX"
                confidence = sensex_score
            else:
                selected_market = None
                confidence = 0
            
            gate_results.append(GateResult(
                gate_name="MARKET_COMPARISON",
                status=GateStatus.PASS if selected_market else GateStatus.FAIL,
                score=confidence,
                reason=f"Selected: {selected_market or 'NONE'}"
            ))
            if not selected_market:
                return self._no_trade_result(market, "No clear winner between markets", gate_results)
            if selected_market != market:
                return self._no_trade_result(market, f"Market comparison selected {selected_market}", gate_results)
            reasons.append(f"Market selected: {selected_market}")
        except ImportError as e:
            self.logger.warning(f"Market comparison not available: {e}")
            gate_results.append(GateResult(
                gate_name="MARKET_COMPARISON",
                status=GateStatus.PASS,
                score=50,
                reason="Market comparison skipped (not available)"
            ))
        
        # GATE 6: OPTIONS STRUCTURE
        options_score, gate_result = self._gate_options_structure(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Options structure unfavorable", gate_results)
        reasons.append(gate_result.reason)
        
        # GATE 7: TECHNICAL CONFIRMATION
        technical_score, gate_result = self._gate_technical_confirmation(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Technical confirmation failed", gate_results)
        reasons.append(gate_result.reason)
        
        # GATE 7.5: MARKET BREADTH
        try:
            from services.broader_market_intelligence.breadth import evaluate_market_breadth
            from services.contracts.market_breadth_snapshot_v1 import MarketBreadthSnapshotV1
            
            breadth_snapshot = MarketBreadthSnapshotV1(
                underlying_symbol=market,
                exchange="NSE" if market == "NIFTY" else "BSE",
                source_id=f"breadth_{market}_{datetime.now().timestamp()}",
                source_timestamp=datetime.now(timezone.utc),
                advance_count=data.get("advances", 0),
                decline_count=data.get("declines", 0),
                unchanged_count=data.get("unchanged", 0),
                total_count=data.get("total_stocks", 100),
                covered_count=data.get("covered_stocks", 50),
                is_partial=False,
                warnings=()
            )
            
            breadth_result = evaluate_market_breadth(
                breadth_snapshot=breadth_snapshot,
                created_at=datetime.now(timezone.utc),
                evidence_id=f"breadth_evidence_{market}_{datetime.now().timestamp()}"
            )
            if breadth_result:
                gate_results.append(GateResult(
                    gate_name="MARKET_BREADTH",
                    status=GateStatus.PASS,
                    score=breadth_result.strength * 100 if breadth_result.strength else 50,
                    reason=f"Breadth: {breadth_result.bias or 'NEUTRAL'}"
                ))
                if breadth_result.bias == "BEARISH":
                    reasons.append("Weak market breadth - reducing confidence")
                    confidence_multiplier = 0.8
                else:
                    confidence_multiplier = 1.0
            else:
                confidence_multiplier = 1.0
        except ImportError as e:
            self.logger.warning(f"Market breadth not available: {e}")
            confidence_multiplier = 1.0
            gate_results.append(GateResult(
                gate_name="MARKET_BREADTH",
                status=GateStatus.PASS,
                score=50,
                reason="Market breadth skipped (not available)"
            ))
        
        # GATE 8: LIQUIDITY / SPREAD
        gate_result = self._gate_liquidity(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Liquidity insufficient", gate_results)
        reasons.append(gate_result.reason)
        
        # GATE 9: RISK / REWARD
        risk_reward, gate_result = self._gate_risk_reward(data)
        gate_results.append(gate_result)
        if gate_result.status == GateStatus.BLOCK:
            return self._no_trade_result(market, "Risk/reward insufficient", gate_results)
        reasons.append(gate_result.reason)
        
        # Calculate final decision
        composite_score, decision, confidence = self._calculate_final_decision(
            global_score=global_score,
            regime_score=regime_score,
            options_score=options_score,
            technical_score=technical_score,
            risk_reward=risk_reward
        )
        
        # Apply confidence multiplier from breadth
        confidence = confidence * confidence_multiplier
        
        if confidence < self.min_confidence:
            return self._no_trade_result(
                market, 
                f"Insufficient confidence: {confidence:.1f} < {self.min_confidence}", 
                gate_results
            )
        
        return PipelineResult(
            market=market,
            action=DecisionAction.BUY_CALL if decision == "CALL" else DecisionAction.BUY_PUT,
            confidence=confidence,
            composite_score=composite_score,
            gate_results=gate_results,
            reasons=reasons + [f"Confidence: {confidence:.1f}%"],
            technical_score=technical_score,
            options_score=options_score,
            regime_score=regime_score,
            global_score=global_score,
            entry_price=data.get("entry_price"),
            stop_loss=data.get("stop_loss"),
            target1=data.get("target1"),
            target2=data.get("target2"),
            target3=data.get("target3"),
            option_contract=data.get("option_contract"),
            strike=data.get("strike"),
            expiry=data.get("expiry")
        )
    
    def _gate_data_validity(self, data: Dict) -> GateResult:
        required = ["price", "timestamp"]
        missing = [f for f in required if f not in data or data[f] is None]
        if missing:
            return GateResult(
                gate_name="DATA_VALIDITY",
                status=GateStatus.BLOCK,
                reason=f"Missing data: {', '.join(missing)}"
            )
        return GateResult(
            gate_name="DATA_VALIDITY",
            status=GateStatus.PASS,
            score=100,
            reason="Data valid"
        )
    
    def _gate_market_session(self, data: Dict) -> GateResult:
        is_open = data.get("market_open", True)
        if not is_open:
            return GateResult(
                gate_name="MARKET_SESSION",
                status=GateStatus.BLOCK,
                reason="Market is closed"
            )
        return GateResult(
            gate_name="MARKET_SESSION",
            status=GateStatus.PASS,
            score=100,
            reason="Market session open"
        )
    
    def _gate_global_environment(self, data: Dict) -> Tuple[float, GateResult]:
        score = 50
        reasons = []
        
        global_trend = data.get("global_trend", "NEUTRAL")
        if global_trend == "BULLISH":
            score += 20
            reasons.append("Global markets bullish")
        elif global_trend == "BEARISH":
            score -= 20
            reasons.append("Global markets bearish")
        
        news_sentiment = data.get("news_sentiment", 0)
        if news_sentiment > 0.3:
            score += 15
            reasons.append("Positive news sentiment")
        elif news_sentiment < -0.3:
            score -= 15
            reasons.append("Negative news sentiment")
        
        high_impact_event = data.get("high_impact_event", False)
        if high_impact_event:
            score -= 30
            reasons.append("High-impact event pending")
        
        score = max(0, min(100, score))
        
        if score < 30:
            return score, GateResult(
                gate_name="GLOBAL_ENVIRONMENT",
                status=GateStatus.BLOCK,
                score=score,
                reason=" | ".join(reasons) if reasons else "Global environment unfavorable"
            )
        
        return score, GateResult(
            gate_name="GLOBAL_ENVIRONMENT",
            status=GateStatus.PASS,
            score=score,
            reason=" | ".join(reasons) if reasons else "Global environment neutral"
        )
    
    def _gate_market_regime(self, data: Dict) -> Tuple[float, GateResult]:
        regime = data.get("regime", "RANGE")
        regime_scores = {
            "STRONG_BULL": 90, "BULL": 80, "WEAK_BULL": 65,
            "RANGE": 50, "WEAK_BEAR": 35, "BEAR": 20,
            "STRONG_BEAR": 10, "HIGH_VOLATILITY": 40,
            "EVENT_DRIVEN": 30, "UNSTABLE": 20,
        }
        score = regime_scores.get(regime, 50)
        if regime in ["STRONG_BEAR", "BEAR", "UNSTABLE"]:
            return score, GateResult(
                gate_name="MARKET_REGIME",
                status=GateStatus.BLOCK,
                score=score,
                reason=f"Unfavorable regime: {regime}"
            )
        return score, GateResult(
            gate_name="MARKET_REGIME",
            status=GateStatus.PASS,
            score=score,
            reason=f"Regime: {regime}"
        )
    
    def _gate_options_structure(self, data: Dict) -> Tuple[float, GateResult]:
        score = 50
        reasons = []
        
        pcr = data.get("pcr", 1.0)
        if 0.8 <= pcr <= 1.2:
            score += 20
            reasons.append(f"PCR neutral: {pcr:.2f}")
        elif pcr > 1.2:
            score -= 20
            reasons.append(f"PCR bearish: {pcr:.2f}")
        else:
            score += 10
            reasons.append(f"PCR bullish: {pcr:.2f}")
        
        score = max(0, min(100, score))
        if score < self.min_options_score:
            return score, GateResult(
                gate_name="OPTIONS_STRUCTURE",
                status=GateStatus.BLOCK,
                score=score,
                reason=" | ".join(reasons) if reasons else "Options structure unfavorable"
            )
        return score, GateResult(
            gate_name="OPTIONS_STRUCTURE",
            status=GateStatus.PASS,
            score=score,
            reason=" | ".join(reasons) if reasons else "Options structure neutral"
        )
    
    def _gate_technical_confirmation(self, data: Dict) -> Tuple[float, GateResult]:
        score = 50
        reasons = []
        
        rsi = data.get("rsi", 50)
        if 40 <= rsi <= 60:
            score += 10
            reasons.append(f"RSI neutral: {rsi:.1f}")
        elif rsi > 70:
            score -= 10
            reasons.append(f"RSI overbought: {rsi:.1f}")
        elif rsi < 30:
            score += 10
            reasons.append(f"RSI oversold: {rsi:.1f}")
        
        macd = data.get("macd", 0)
        if macd > 0:
            score += 10
            reasons.append("MACD bullish")
        else:
            score -= 10
            reasons.append("MACD bearish")
        
        adx = data.get("adx", 0)
        if adx > 25:
            score += 10
            reasons.append(f"Strong trend: ADX {adx:.1f}")
        
        score = max(0, min(100, score))
        if score < self.min_technical_score:
            return score, GateResult(
                gate_name="TECHNICAL_CONFIRMATION",
                status=GateStatus.BLOCK,
                score=score,
                reason=" | ".join(reasons) if reasons else "Technical confirmation failed"
            )
        return score, GateResult(
            gate_name="TECHNICAL_CONFIRMATION",
            status=GateStatus.PASS,
            score=score,
            reason=" | ".join(reasons) if reasons else "Technical confirmation passed"
        )
    
    def _gate_liquidity(self, data: Dict) -> GateResult:
        volume = data.get("volume", 0)
        if volume < 100000:
            return GateResult(
                gate_name="LIQUIDITY",
                status=GateStatus.BLOCK,
                reason=f"Volume too low: {volume:,}"
            )
        return GateResult(
            gate_name="LIQUIDITY",
            status=GateStatus.PASS,
            score=100,
            reason=f"Volume: {volume:,}"
        )
    
    def _gate_risk_reward(self, data: Dict) -> Tuple[float, GateResult]:
        entry = data.get("entry_price", 0)
        stop = data.get("stop_loss", entry * 0.98)
        target = data.get("target_price", entry * 1.02)
        
        if entry <= 0:
            return 0, GateResult(
                gate_name="RISK_REWARD",
                status=GateStatus.BLOCK,
                reason="No entry price"
            )
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk <= 0:
            return 0, GateResult(
                gate_name="RISK_REWARD",
                status=GateStatus.BLOCK,
                reason="Invalid risk calculation"
            )
        
        rr_ratio = reward / risk
        if rr_ratio < self.min_risk_reward:
            return rr_ratio, GateResult(
                gate_name="RISK_REWARD",
                status=GateStatus.BLOCK,
                reason=f"Risk/Reward too low: {rr_ratio:.2f}"
            )
        
        score = min(100, 40 + (rr_ratio - 1.5) * 20)
        return rr_ratio, GateResult(
            gate_name="RISK_REWARD",
            status=GateStatus.PASS,
            score=score,
            reason=f"Risk/Reward: {rr_ratio:.2f}"
        )
    
    def _calculate_final_decision(self, **scores) -> Tuple[float, str, float]:
        weights = {
            "global_score": 0.10,
            "regime_score": 0.15,
            "options_score": 0.20,
            "technical_score": 0.25,
            "risk_reward": 0.10,
        }
        
        risk_reward = scores.get("risk_reward", 0)
        scores["risk_reward"] = min(100, risk_reward * 25)
        
        composite = sum(scores.get(key, 0) * weight for key, weight in weights.items())
        
        bullish_score = (scores.get("technical_score", 50) + scores.get("options_score", 50)) / 2
        bearish_score = 100 - bullish_score
        
        if bullish_score > bearish_score + 15:
            decision = "CALL"
        elif bearish_score > bullish_score + 15:
            decision = "PUT"
        else:
            decision = "NEUTRAL"
        
        confidence = composite if decision != "NEUTRAL" else 0
        return composite, decision, confidence
    
    def _no_trade_result(self, market: str, reason: str, gate_results: List[GateResult]) -> PipelineResult:
        return PipelineResult(
            market=market,
            action=DecisionAction.NO_TRADE,
            confidence=0,
            composite_score=0,
            gate_results=gate_results,
            reasons=[reason],
            technical_score=0,
            options_score=0,
            regime_score=0,
            global_score=0
        )
