# services/trade_planning/capital_safe_recommendation_runtime.py
# FIXED: Uses premium-based capital validation

import logging
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

# LOT SIZES (SEBI 2026)
LOT_SIZES = {
    'NIFTY': 65,
    'SENSEX': 20,
    'BANKNIFTY': 25,
    'FINNIFTY': 40
}

class CapitalSafeRecommendationRuntime:
    """
    Validates trade recommendations against available capital.
    Uses PREMIUM-based calculations.
    """
    
    def __init__(self, total_capital: float = 1000000):
        self.total_capital = total_capital
        self.max_usage_percent = 0.80  # Max 80% deployed
    
    def validate_recommendation(
        self,
        recommendation: Dict[str, Any],
        existing_positions: list = None
    ) -> Dict[str, Any]:
        """
        Validate a trade recommendation against capital.
        
        IMPORTANT: Uses PREMIUM for cost calculation.
        """
        existing_positions = existing_positions or []
        
        # Get recommendation details
        symbol = recommendation.get('symbol', 'NIFTY')
        lots = recommendation.get('lots', 0)
        premium = recommendation.get('entry_premium', recommendation.get('entry_price', 0))
        
        # Get lot size
        lot_size = LOT_SIZES.get(symbol, 65)
        quantity = lots * lot_size
        
        # Calculate cost using premium
        cost = premium * quantity
        
        # Calculate existing deployed capital
        existing_deployed = 0
        for pos in existing_positions:
            if pos.get('status') == 'OPEN':
                pos_premium = pos.get('entry_premium', pos.get('entry_price', 0))
                pos_quantity = pos.get('quantity', 0)
                existing_deployed += pos_premium * pos_quantity
        
        # Total after adding this position
        total_after = existing_deployed + cost
        usage_percent = (total_after / self.total_capital) * 100 if self.total_capital > 0 else 0
        
        # Validate
        is_valid = True
        reasons = []
        
        if cost <= 0:
            is_valid = False
            reasons.append(f"Invalid premium: ₹{premium}")
        
        if total_after > self.total_capital:
            is_valid = False
            reasons.append(
                f"Insufficient capital: Need ₹{cost:,.2f}, "
                f"available ₹{self.total_capital - existing_deployed:,.2f}"
            )
        
        if usage_percent > self.max_usage_percent * 100:
            is_valid = False
            reasons.append(
                f"Would exceed max usage: {usage_percent:.1f}% > {self.max_usage_percent * 100:.0f}%"
            )
        
        return {
            'valid': is_valid,
            'reasons': reasons,
            'cost': cost,
            'total_deployed_after': total_after,
            'usage_percent': usage_percent,
            'available_capital': self.total_capital - existing_deployed,
            'symbol': symbol,
            'lots': lots,
            'lot_size': lot_size,
            'quantity': quantity,
            'premium': premium
        }
    
    def calculate_position_affordability(
        self,
        premium: float,
        lots: int,
        symbol: str = 'NIFTY'
    ) -> Dict[str, Any]:
        """
        Calculate if a position is affordable.
        """
        lot_size = LOT_SIZES.get(symbol, 65)
        quantity = lots * lot_size
        cost = premium * quantity
        
        return {
            'affordable': cost <= self.total_capital * self.max_usage_percent,
            'cost': cost,
            'usage_percent': (cost / self.total_capital) * 100 if self.total_capital > 0 else 0,
            'lot_size': lot_size,
            'quantity': quantity,
            'premium': premium
        }
