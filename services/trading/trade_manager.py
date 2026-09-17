"""
Trade Manager - PDF Sections 28-29
HOLD / WAIT / EXIT state machine with prediction invalidation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
import logging


class TradeAction(Enum):
    HOLD = "HOLD"
    WAIT = "WAIT"
    EXIT = "EXIT"


class ExitReason(Enum):
    """PDF Section 30 - Exit Reason Codes"""
    TARGET_1 = "TARGET_1"
    TARGET_2 = "TARGET_2"
    TARGET_3 = "TARGET_3"
    PREDICTION_INVALIDATED = "PREDICTION_INVALIDATED"
    STOP_LOSS = "STOP_LOSS"
    TIME_EXIT = "TIME_EXIT"
    LIQUIDITY_EXIT = "LIQUIDITY_EXIT"
    EVENT_RISK = "EVENT_RISK"
    MARKET_CLOSE = "MARKET_CLOSE"
    DATA_FAILURE = "DATA_FAILURE"
    SYSTEM_SAFETY = "SYSTEM_SAFETY"
    MANUAL_EXIT = "MANUAL_EXIT"


@dataclass
class TradeManagementDecision:
    """Decision from trade management engine."""
    trade_id: str
    action: TradeAction
    reason: str
    exit_reason: Optional[ExitReason] = None
    health_score: Optional[float] = None
    invalidation_conditions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    should_exit: bool = False


@dataclass
class TradeThesis:
    """Thesis for an active trade."""
    trade_id: str
    entry_price: float
    stop_loss: float
    targets: List[float]
    invalidation_conditions: List[str]
    entry_time: datetime
    max_hold_minutes: int = 60  # Default max hold time
    last_updated: datetime = field(default_factory=datetime.now)


class TradeManager:
    """
    Trade Manager - PDF Sections 28-29.
    
    HOLD / WAIT / EXIT with prediction invalidation detection.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self._active_theses: Dict[str, TradeThesis] = {}
        self._exit_history: Dict[str, List[Dict]] = {}
        
        # Thresholds
        self.health_thresholds = {
            "exit_immediate": 25,
            "exit_consider": 40,
            "wait": 55,
            "hold": 70,
        }
        # Update with config if provided
        if self.config and "thresholds" in self.config:
            self.health_thresholds.update(self.config["thresholds"])
    
    def register_trade(self, trade_id: str, thesis_data: Dict) -> TradeThesis:
        """Register a new trade with its thesis."""
        thesis = TradeThesis(
            trade_id=trade_id,
            entry_price=thesis_data.get("entry_price", 0),
            stop_loss=thesis_data.get("stop_loss", 0),
            targets=thesis_data.get("targets", []),
            invalidation_conditions=thesis_data.get("invalidation_conditions", []),
            entry_time=datetime.now(),
            max_hold_minutes=thesis_data.get("max_hold_minutes", 60)
        )
        
        self._active_theses[trade_id] = thesis
        self._exit_history[trade_id] = []
        
        self.logger.info(f"Registered trade thesis for {trade_id}")
        return thesis
    
    def evaluate(self, trade_id: str, health, data: Dict) -> TradeManagementDecision:
        """
        Evaluate HOLD / WAIT / EXIT.
        
        Args:
            trade_id: The trade ID
            health: HealthScore from PredictionHealthMonitor
            data: Current market data
            
        Returns:
            TradeManagementDecision with action
        """
        thesis = self._active_theses.get(trade_id)
        if not thesis:
            return TradeManagementDecision(
                trade_id=trade_id,
                action=TradeAction.EXIT,
                reason="Thesis not found",
                exit_reason=ExitReason.SYSTEM_SAFETY,
                should_exit=True
            )
        
        # Check invalidation
        is_invalidated, invalid_reasons = self._check_invalidation(
            thesis.invalidation_conditions,
            data
        )
        
        if is_invalidated:
            self.logger.warning(f"Trade {trade_id} invalidated: {invalid_reasons}")
            return TradeManagementDecision(
                trade_id=trade_id,
                action=TradeAction.EXIT,
                reason="PREDICTION_INVALIDATED",
                exit_reason=ExitReason.PREDICTION_INVALIDATED,
                health_score=health.current_score,
                invalidation_conditions=invalid_reasons,
                should_exit=True
            )
        
        # Check health thresholds
        health_score = health.current_score
        
        # IMMEDIATE EXIT - Health critical
        if health_score < self.health_thresholds["exit_immediate"]:
            return TradeManagementDecision(
                trade_id=trade_id,
                action=TradeAction.EXIT,
                reason=f"Critical health: {health_score:.1f}",
                exit_reason=ExitReason.STOP_LOSS,
                health_score=health_score,
                should_exit=True
            )
        
        # CONSIDER EXIT - Health weak
        if health_score < self.health_thresholds["exit_consider"]:
            # Check if price is moving against us
            price = data.get("price", 0)
            if price < thesis.entry_price:
                return TradeManagementDecision(
                    trade_id=trade_id,
                    action=TradeAction.EXIT,
                    reason=f"Weak health + price below entry: {health_score:.1f}",
                    exit_reason=ExitReason.PREDICTION_INVALIDATED,
                    health_score=health_score,
                    should_exit=True
                )
            else:
                # Wait for confirmation
                return TradeManagementDecision(
                    trade_id=trade_id,
                    action=TradeAction.WAIT,
                    reason=f"Weak health but price holding: {health_score:.1f}",
                    health_score=health_score,
                    should_exit=False
                )
        
        # WAIT - Health fair
        if health_score < self.health_thresholds["wait"]:
            # Check if health is improving or deteriorating
            if health.is_deteriorating:
                return TradeManagementDecision(
                    trade_id=trade_id,
                    action=TradeAction.WAIT,
                    reason=f"Health deteriorating: {health_score:.1f}",
                    health_score=health_score,
                    should_exit=False
                )
            else:
                return TradeManagementDecision(
                    trade_id=trade_id,
                    action=TradeAction.HOLD,
                    reason=f"Health stable: {health_score:.1f}",
                    health_score=health_score,
                    should_exit=False
                )
        
        # Check time limit
        hold_minutes = (datetime.now() - thesis.entry_time).total_seconds() / 60
        if hold_minutes > thesis.max_hold_minutes:
            return TradeManagementDecision(
                trade_id=trade_id,
                action=TradeAction.EXIT,
                reason=f"Time limit exceeded: {hold_minutes:.1f} mins",
                exit_reason=ExitReason.TIME_EXIT,
                health_score=health_score,
                should_exit=True
            )
        
        # Check stop loss
        price = data.get("price", 0)
        if price <= thesis.stop_loss:
            return TradeManagementDecision(
                trade_id=trade_id,
                action=TradeAction.EXIT,
                reason=f"Stop loss hit: {price:.2f}",
                exit_reason=ExitReason.STOP_LOSS,
                health_score=health_score,
                should_exit=True
            )
        
        # DEFAULT: HOLD
        return TradeManagementDecision(
            trade_id=trade_id,
            action=TradeAction.HOLD,
            reason=f"Thesis valid: health={health_score:.1f}",
            health_score=health_score,
            should_exit=False
        )
    
    def _check_invalidation(self, conditions: List[str], data: Dict) -> Tuple[bool, List[str]]:
        """
        PDF Section 29 - Check if prediction is invalidated.
        
        Examples:
        - Bullish breakout failed
        - Price below VWAP
        - Put support removed
        - Volume confirms selling
        """
        invalid_reasons = []
        is_invalidated = False
        
        for condition in conditions:
            if self._evaluate_condition(condition, data):
                invalid_reasons.append(condition)
                is_invalidated = True
        
        return is_invalidated, invalid_reasons
    
    def _evaluate_condition(self, condition: str, data: Dict) -> bool:
        """Evaluate a single invalidation condition."""
        price = data.get("price", 0)
        vwap = data.get("vwap", price)
        support = data.get("support", 0)
        resistance = data.get("resistance", 0)
        volume_ratio = data.get("volume_ratio", 1.0)
        pcr = data.get("pcr", 1.0)
        
        # Price-based conditions
        if condition == "price_below_vwap":
            return price < vwap
        
        if condition == "price_above_vwap":
            return price > vwap
        
        if condition == "support_broken":
            return support > 0 and price < support
        
        if condition == "resistance_holding":
            return resistance > 0 and price < resistance
        
        if condition == "resistance_broken":
            return resistance > 0 and price > resistance
        
        # Volume conditions
        if condition == "volume_confirms_selling":
            return volume_ratio < 0.5
        
        if condition == "volume_confirms_buying":
            return volume_ratio > 1.5
        
        # Options conditions
        if condition == "pcr_turned_bearish":
            return pcr > 1.2
        
        if condition == "pcr_turned_bullish":
            return pcr < 0.8
        
        # Multi-condition support
        if condition == "bullish_breakout_failed":
            # Check if we broke above resistance but failed to hold
            resistance = data.get("resistance", 0)
            if resistance > 0:
                # Check if price broke above but then fell back
                high = data.get("high", price)
                if high > resistance * 1.01 and price < resistance * 1.01:
                    return True
            return False
        
        return False
    
    def record_exit(self, trade_id: str, decision: TradeManagementDecision):
        """Record an exit decision for analysis."""
        if trade_id not in self._exit_history:
            self._exit_history[trade_id] = []
        
        self._exit_history[trade_id].append({
            "timestamp": decision.timestamp.isoformat(),
            "action": decision.action.value,
            "reason": decision.reason,
            "exit_reason": decision.exit_reason.value if decision.exit_reason else None,
            "health_score": decision.health_score,
            "invalidation_conditions": decision.invalidation_conditions
        })
        
        # Remove from active theses
        self._active_theses.pop(trade_id, None)
    
    def get_active_thesis(self, trade_id: str) -> Optional[TradeThesis]:
        """Get the active thesis for a trade."""
        return self._active_theses.get(trade_id)
    
    def get_exit_history(self, trade_id: str) -> List[Dict]:
        """Get exit history for a trade."""
        return self._exit_history.get(trade_id, [])
    
    def get_all_active_trades(self) -> List[str]:
        """Get all active trade IDs."""
        return list(self._active_theses.keys())