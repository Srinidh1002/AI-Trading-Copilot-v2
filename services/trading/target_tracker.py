"""
Target Tracker - PDF Section 25
T1 (15%), T2 (30%), T3 (50%) target tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import logging


class TargetLevel(Enum):
    T1 = "TARGET_1"  # 15%
    T2 = "TARGET_2"  # 30%
    T3 = "TARGET_3"  # 50%


@dataclass
class TargetStatus:
    """Status of a single target."""
    level: TargetLevel
    target_price: float
    target_percent: float
    is_reached: bool = False
    reached_at: Optional[datetime] = None
    quantity_hit: int = 0


@dataclass
class TradeTargets:
    """Complete target tracking for a trade."""
    trade_id: str
    entry_price: float
    quantity: int
    t1: TargetStatus
    t2: TargetStatus
    t3: TargetStatus
    current_price: float
    max_price: float = 0.0
    targets_hit: int = 0
    is_complete: bool = False
    last_updated: datetime = field(default_factory=datetime.now)


class TargetTracker:
    """
    Three-Target System - PDF Section 25.
    T1: +15%, T2: +30%, T3: +50% of deployed capital.
    """
    
    TARGET_PERCENTS = {
        "T1": 15.0,
        "T2": 30.0,
        "T3": 50.0,
    }
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self._trades: Dict[str, TradeTargets] = {}
        self._target_hit_history: Dict[str, List[str]] = {}
    
    def initialize_trade(self, trade_id: str, entry_price: float, quantity: int) -> TradeTargets:
        """Initialize targets for a new trade."""
        t1_price = entry_price * (1 + self.TARGET_PERCENTS["T1"] / 100)
        t2_price = entry_price * (1 + self.TARGET_PERCENTS["T2"] / 100)
        t3_price = entry_price * (1 + self.TARGET_PERCENTS["T3"] / 100)
        
        targets = TradeTargets(
            trade_id=trade_id,
            entry_price=entry_price,
            quantity=quantity,
            t1=TargetStatus(
                level=TargetLevel.T1,
                target_price=t1_price,
                target_percent=self.TARGET_PERCENTS["T1"]
            ),
            t2=TargetStatus(
                level=TargetLevel.T2,
                target_price=t2_price,
                target_percent=self.TARGET_PERCENTS["T2"]
            ),
            t3=TargetStatus(
                level=TargetLevel.T3,
                target_price=t3_price,
                target_percent=self.TARGET_PERCENTS["T3"]
            ),
            current_price=entry_price,
            max_price=entry_price
        )
        
        self._trades[trade_id] = targets
        self._target_hit_history[trade_id] = []
        
        self.logger.info(f"Initialized targets for trade {trade_id}: T1={t1_price:.2f}, T2={t2_price:.2f}, T3={t3_price:.2f}")
        
        return targets
    
    def check_targets(self, trade_id: str, data: Dict) -> Optional[str]:
        """Check if any target has been reached."""
        targets = self._trades.get(trade_id)
        if not targets:
            return None
        
        current_price = data.get("price", 0)
        if current_price <= 0:
            return None
        
        targets.current_price = current_price
        
        # Update max price
        if current_price > targets.max_price:
            targets.max_price = current_price
        
        # Check each target in order
        for target in [targets.t1, targets.t2, targets.t3]:
            if not target.is_reached and current_price >= target.target_price:
                target.is_reached = True
                target.reached_at = datetime.now()
                targets.targets_hit += 1
                self._target_hit_history[trade_id].append(target.level.value)
                
                self.logger.info(f"Target {target.level.value} reached for trade {trade_id} at {current_price:.2f}")
                
                if targets.targets_hit >= 3:
                    targets.is_complete = True
                    self.logger.info(f"All targets complete for trade {trade_id}")
                
                return target.level.value
        
        return None
    
    def record_hit(self, trade_id: str, target: str):
        """Record a target hit."""
        if trade_id not in self._target_hit_history:
            self._target_hit_history[trade_id] = []
        if target not in self._target_hit_history[trade_id]:
            self._target_hit_history[trade_id].append(target)
    
    def get_targets(self, trade_id: str) -> Optional[TradeTargets]:
        """Get targets for a trade."""
        return self._trades.get(trade_id)
    
    def get_hit_count(self, trade_id: str) -> int:
        """Get number of targets hit for a trade."""
        targets = self._trades.get(trade_id)
        if not targets:
            return 0
        return targets.targets_hit
    
    def get_hit_rate(self, trade_id: str) -> float:
        """Get hit rate for a trade."""
        targets = self._trades.get(trade_id)
        if not targets:
            return 0.0
        return (targets.targets_hit / 3) * 100
    
    def get_next_target(self, trade_id: str) -> Optional[TargetStatus]:
        """Get the next unreached target."""
        targets = self._trades.get(trade_id)
        if not targets:
            return None
        
        for target in [targets.t1, targets.t2, targets.t3]:
            if not target.is_reached:
                return target
        return None
    
    def get_pnl_at_target(self, trade_id: str, target_level: TargetLevel) -> float:
        """Calculate P&L at a specific target."""
        targets = self._trades.get(trade_id)
        if not targets:
            return 0.0
        
        target_map = {
            TargetLevel.T1: targets.t1,
            TargetLevel.T2: targets.t2,
            TargetLevel.T3: targets.t3,
        }
        
        target = target_map.get(target_level)
        if not target:
            return 0.0
        
        # P&L = (target_price - entry_price) * quantity
        pnl = (target.target_price - targets.entry_price) * targets.quantity
        return pnl
    
    def get_total_target_pnl(self, trade_id: str) -> float:
        """Get total P&L if all targets are hit."""
        targets = self._trades.get(trade_id)
        if not targets:
            return 0.0
        
        total_pnl = 0
        for target in [targets.t1, targets.t2, targets.t3]:
            total_pnl += (target.target_price - targets.entry_price) * targets.quantity
        
        return total_pnl
    
    def get_target_status(self, trade_id: str) -> Dict:
        """Get target status for a trade."""
        targets = self._trades.get(trade_id)
        if not targets:
            return {}
        
        return {
            "trade_id": trade_id,
            "entry_price": targets.entry_price,
            "current_price": targets.current_price,
            "t1": {
                "target_price": targets.t1.target_price,
                "is_reached": targets.t1.is_reached,
                "reached_at": targets.t1.reached_at.isoformat() if targets.t1.reached_at else None
            },
            "t2": {
                "target_price": targets.t2.target_price,
                "is_reached": targets.t2.is_reached,
                "reached_at": targets.t2.reached_at.isoformat() if targets.t2.reached_at else None
            },
            "t3": {
                "target_price": targets.t3.target_price,
                "is_reached": targets.t3.is_reached,
                "reached_at": targets.t3.reached_at.isoformat() if targets.t3.reached_at else None
            },
            "targets_hit": targets.targets_hit,
            "is_complete": targets.is_complete,
            "last_updated": targets.last_updated.isoformat()
        }