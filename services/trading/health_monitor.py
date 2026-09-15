"""
Prediction Health Monitor - PDF Sections 26-27
Continuous monitoring of active trades with health scoring.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import logging


class HealthStatus(Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    WEAK = "WEAK"
    CRITICAL = "CRITICAL"


@dataclass
class HealthScore:
    """Health score for an active trade."""
    trade_id: str
    market: str
    direction: str
    initial_score: float
    current_score: float
    trend_score: float
    momentum_score: float
    volume_score: float
    options_score: float
    regime_score: float
    vwap_score: float
    status: HealthStatus
    deterioration_ratio: float
    is_deteriorating: bool
    reasons: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    
    def is_invalidated(self) -> bool:
        """Check if the trade thesis is invalidated."""
        return self.status in [HealthStatus.WEAK, HealthStatus.CRITICAL]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for persistence."""
        return {
            "trade_id": self.trade_id,
            "market": self.market,
            "direction": self.direction,
            "initial_score": self.initial_score,
            "current_score": self.current_score,
            "status": self.status.value,
            "deterioration_ratio": self.deterioration_ratio,
            "is_deteriorating": self.is_deteriorating,
            "reasons": self.reasons,
            "last_updated": self.last_updated.isoformat()
        }


class PredictionHealthMonitor:
    """
    Prediction Health Monitor.
    
    Continuously monitors active trades and calculates health scores.
    PDF Sections 26-27.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}  # Ensure config is always a dict
        self.logger = logging.getLogger(__name__)
        self._health_scores: Dict[str, HealthScore] = {}
        
        # Default thresholds (PDF Section 27)
        self.thresholds = {
            "excellent": 85,
            "good": 70,
            "fair": 55,
            "weak": 40,
            "critical": 25,
        }
        # Update with config if provided
        if self.config and "thresholds" in self.config:
            self.thresholds.update(self.config["thresholds"])
    
    def initialize(self, trade_id: str, data: Dict) -> HealthScore:
        """Initialize health score at trade entry."""
        self.logger.info(f"Initializing health for trade: {trade_id}")
        
        # Calculate initial scores
        initial_score = self._calculate_initial_score(data)
        
        health = HealthScore(
            trade_id=trade_id,
            market=data.get("market", "NIFTY"),
            direction=data.get("direction", "CALL"),
            initial_score=initial_score,
            current_score=initial_score,
            trend_score=self._score_trend(data),
            momentum_score=self._score_momentum(data),
            volume_score=self._score_volume(data),
            options_score=self._score_options(data),
            regime_score=self._score_regime(data),
            vwap_score=self._score_vwap(data),
            status=self._determine_status(initial_score),
            deterioration_ratio=1.0,
            is_deteriorating=False,
            reasons=["Trade entry - initial health assessment"]
        )
        
        self._health_scores[trade_id] = health
        return health
    
    def update(self, trade_id: str, data: Dict) -> HealthScore:
        """Update health score for an active trade."""
        current = self._health_scores.get(trade_id)
        if not current:
            self.logger.warning(f"No health record for trade: {trade_id}")
            return self.initialize(trade_id, data)
        
        # Calculate individual scores
        trend_score = self._score_trend(data)
        momentum_score = self._score_momentum(data)
        volume_score = self._score_volume(data)
        options_score = self._score_options(data)
        regime_score = self._score_regime(data)
        vwap_score = self._score_vwap(data)
        
        # Weighted composite
        weights = {
            "trend": 0.20,
            "momentum": 0.15,
            "volume": 0.15,
            "options": 0.20,
            "regime": 0.15,
            "vwap": 0.15,
        }
        
        current_score = (
            trend_score * weights["trend"] +
            momentum_score * weights["momentum"] +
            volume_score * weights["volume"] +
            options_score * weights["options"] +
            regime_score * weights["regime"] +
            vwap_score * weights["vwap"]
        )
        
        # Calculate deterioration
        deterioration_ratio = current_score / current.initial_score if current.initial_score > 0 else 1.0
        
        # Determine status
        status = self._determine_status(current_score)
        
        # Build reasons
        reasons = self._build_reasons(data)
        
        # Update health
        health = HealthScore(
            trade_id=trade_id,
            market=current.market,
            direction=current.direction,
            initial_score=current.initial_score,
            current_score=current_score,
            trend_score=trend_score,
            momentum_score=momentum_score,
            volume_score=volume_score,
            options_score=options_score,
            regime_score=regime_score,
            vwap_score=vwap_score,
            status=status,
            deterioration_ratio=deterioration_ratio,
            is_deteriorating=deterioration_ratio < 0.85,
            reasons=reasons
        )
        
        self._health_scores[trade_id] = health
        
        # Log deterioration
        if health.is_deteriorating:
            self.logger.warning(
                f"Trade {trade_id} deteriorating: {current_score:.1f} from {current.initial_score:.1f}"
            )
        
        return health
    
    def get_health(self, trade_id: str) -> Optional[HealthScore]:
        """Get current health score for a trade."""
        return self._health_scores.get(trade_id)
    
    def is_healthy(self, trade_id: str) -> bool:
        """Check if a trade is still healthy."""
        health = self.get_health(trade_id)
        if not health:
            return False
        return health.status not in [HealthStatus.WEAK, HealthStatus.CRITICAL]
    
    def _calculate_initial_score(self, data: Dict) -> float:
        """Calculate initial health score from entry data."""
        scores = {
            "trend": self._score_trend(data),
            "momentum": self._score_momentum(data),
            "volume": self._score_volume(data),
            "options": self._score_options(data),
            "regime": self._score_regime(data),
            "vwap": self._score_vwap(data),
        }
        return sum(scores.values()) / len(scores) if scores else 75.0
    
    def _score_trend(self, data: Dict) -> float:
        """Score based on trend alignment."""
        trend = data.get("trend", "SIDEWAYS")
        if trend == "STRONG_BULL":
            return 90
        elif trend == "BULLISH":
            return 80
        elif trend == "SIDEWAYS":
            return 50
        elif trend == "BEARISH":
            return 30
        elif trend == "STRONG_BEAR":
            return 10
        return 50
    
    def _score_momentum(self, data: Dict) -> float:
        """Score based on momentum indicators."""
        rsi = data.get("rsi", 50)
        if rsi > 70:
            return 80
        elif rsi > 60:
            return 65
        elif rsi > 40:
            return 50
        elif rsi > 30:
            return 35
        return 20
    
    def _score_volume(self, data: Dict) -> float:
        """Score based on volume confirmation."""
        volume_ratio = data.get("volume_ratio", 1.0)
        if volume_ratio > 1.5:
            return 85
        elif volume_ratio > 1.0:
            return 70
        elif volume_ratio > 0.5:
            return 50
        return 30
    
    def _score_options(self, data: Dict) -> float:
        """Score based on options structure."""
        pcr = data.get("pcr", 1.0)
        if 0.8 <= pcr <= 1.2:
            return 80
        elif 0.6 <= pcr < 0.8:
            return 65
        elif 1.2 < pcr <= 1.4:
            return 65
        return 40
    
    def _score_regime(self, data: Dict) -> float:
        """Score based on market regime."""
        regime = data.get("regime", "RANGE")
        regime_scores = {
            "STRONG_BULL": 90,
            "BULL": 80,
            "WEAK_BULL": 65,
            "RANGE": 50,
            "WEAK_BEAR": 35,
            "BEAR": 20,
            "STRONG_BEAR": 10,
            "HIGH_VOLATILITY": 40,
            "EVENT_DRIVEN": 30,
        }
        return regime_scores.get(regime, 50)
    
    def _score_vwap(self, data: Dict) -> float:
        """Score based on VWAP relationship."""
        price = data.get("price", 0)
        vwap = data.get("vwap", price)
        if price > vwap * 1.005:
            return 80
        elif price > vwap:
            return 65
        elif price > vwap * 0.995:
            return 50
        return 30
    
    def _determine_status(self, score: float) -> HealthStatus:
        """Determine health status based on score."""
        if score >= self.thresholds["excellent"]:
            return HealthStatus.EXCELLENT
        elif score >= self.thresholds["good"]:
            return HealthStatus.GOOD
        elif score >= self.thresholds["fair"]:
            return HealthStatus.FAIR
        elif score >= self.thresholds["weak"]:
            return HealthStatus.WEAK
        return HealthStatus.CRITICAL
    
    def _build_reasons(self, data: Dict) -> List[str]:
        """Build health reasons from data."""
        reasons = []
        
        # Trend
        trend = data.get("trend", "SIDEWAYS")
        if trend in ["STRONG_BULL", "BULLISH"]:
            reasons.append("Trend bullish")
        elif trend in ["STRONG_BEAR", "BEARISH"]:
            reasons.append("Trend bearish")
        else:
            reasons.append("Trend sideways")
        
        # VWAP
        price = data.get("price", 0)
        vwap = data.get("vwap", price)
        if price > vwap:
            reasons.append("Price above VWAP")
        else:
            reasons.append("Price below VWAP")
        
        # RSI
        rsi = data.get("rsi", 50)
        if rsi > 70:
            reasons.append(f"RSI overbought: {rsi:.1f}")
        elif rsi < 30:
            reasons.append(f"RSI oversold: {rsi:.1f}")
        
        # Regime
        regime = data.get("regime", "RANGE")
        reasons.append(f"Regime: {regime}")
        
        return reasons