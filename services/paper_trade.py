# services/paper_trade.py
# FIXED: Paper trade model using premium-based calculations

import json
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from decimal import Decimal

# LOT SIZES (SEBI 2026)
LOT_SIZES = {
    'NIFTY': 65,
    'SENSEX': 20,
    'BANKNIFTY': 25,
    'FINNIFTY': 40
}

@dataclass
class PaperTrade:
    """Paper trade model with premium-based calculations."""
    
    id: str
    symbol: str
    option_type: str  # 'CALL' or 'PUT'
    strike: float
    expiry: str
    lots: int
    entry_premium: float  # This is the OPTION PREMIUM, NOT underlying price
    entry_timestamp: datetime
    status: str = 'OPEN'  # OPEN, TARGET1, TARGET2, TARGET3, STOPPED, CLOSED
    exit_premium: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    stop_premium: Optional[float] = None
    target1_premium: Optional[float] = None
    target2_premium: Optional[float] = None
    target3_premium: Optional[float] = None
    entry_reason: str = ''
    regime: str = 'NEUTRAL'
    confidence: float = 0.5
    hold_count: int = 0
    
    def __post_init__(self):
        # Ensure we have lot size
        self.lot_size = LOT_SIZES.get(self.symbol, 65)
        self.quantity = self.lots * self.lot_size
    
    @property
    def deployed_capital(self) -> float:
        """Actual capital deployed = premium × quantity"""
        return self.entry_premium * self.quantity
    
    @property
    def current_value(self) -> float:
        """Current value based on current premium"""
        if self.exit_premium is not None:
            return self.exit_premium * self.quantity
        return self.entry_premium * self.quantity
    
    def calculate_pnl(self, current_premium: float) -> Dict[str, float]:
        """Calculate P&L for this trade."""
        pnl_amount = (current_premium - self.entry_premium) * self.quantity
        pnl_percent = ((current_premium / self.entry_premium) - 1) * 100 if self.entry_premium > 0 else 0
        
        return {
            'pnl_amount': pnl_amount,
            'pnl_percent': pnl_percent,
            'entry_premium': self.entry_premium,
            'current_premium': current_premium,
            'quantity': self.quantity,
            'deployed': self.deployed_capital
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'option_type': self.option_type,
            'strike': self.strike,
            'expiry': self.expiry,
            'lots': self.lots,
            'lot_size': self.lot_size,
            'quantity': self.quantity,
            'entry_premium': self.entry_premium,
            'entry_price': self.entry_premium,  # Alias for compatibility
            'entry_timestamp': self.entry_timestamp.isoformat() if self.entry_timestamp else None,
            'status': self.status,
            'exit_premium': self.exit_premium,
            'exit_timestamp': self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            'stop_premium': self.stop_premium,
            'target1_premium': self.target1_premium,
            'target2_premium': self.target2_premium,
            'target3_premium': self.target3_premium,
            'entry_reason': self.entry_reason,
            'regime': self.regime,
            'confidence': self.confidence,
            'hold_count': self.hold_count,
            'deployed_capital': self.deployed_capital
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaperTrade':
        """Create from dictionary."""
        data = data.copy()
        
        # Handle timestamp strings
        if 'entry_timestamp' in data and isinstance(data['entry_timestamp'], str):
            data['entry_timestamp'] = datetime.fromisoformat(data['entry_timestamp'])
        if 'exit_timestamp' in data and isinstance(data['exit_timestamp'], str):
            data['exit_timestamp'] = datetime.fromisoformat(data['exit_timestamp'])
        
        # Ensure entry_premium is used
        if 'entry_price' in data and 'entry_premium' not in data:
            data['entry_premium'] = data['entry_price']
        
        return cls(**data)
