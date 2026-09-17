# services/paper_trading/paper_trade_engine.py
# FIXED: Use PREMIUM for entry price, NOT underlying

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperTradeEngine:
    """Paper trading engine with CORRECT premium-based entry."""
    
    def __init__(self, capital: float = 1000000):
        self.capital = capital
        self.max_lots = 10
        self.lot_sizes = {
            "NIFTY": 65,
            "SENSEX": 20
        }
    
    def get_option_premium(self, underlying_price: float, strike: float, option_type: str = "CALL") -> float:
        """
        Get option premium for a given underlying price and strike.
        
        In production, this should call the broker API.
        For testing, we use an approximation.
        """
        if option_type == "CALL":
            moneyness = underlying_price - strike
            if moneyness > 0:
                # ITM: intrinsic + time value
                premium = moneyness + (underlying_price * 0.02)  # 2% time value
            else:
                # OTM: only time value (lower for farther OTM)
                otm_distance = abs(moneyness) / underlying_price
                time_value = underlying_price * (0.02 - otm_distance * 0.5)
                premium = max(time_value, 10)  # Minimum ₹10
        else:
            # PUT option
            moneyness = strike - underlying_price
            if moneyness > 0:
                premium = moneyness + (underlying_price * 0.02)
            else:
                otm_distance = abs(moneyness) / underlying_price
                time_value = underlying_price * (0.02 - otm_distance * 0.5)
                premium = max(time_value, 10)
        
        return round(premium, 2)
    
    def enter_trade(self, symbol: str, option_type: str, strike: float, lots: int, 
                   underlying_price: float, reason: str = "", regime: str = "NEUTRAL") -> Dict[str, Any]:
        """
        Enter a trade using PREMIUM as the entry price.
        
        IMPORTANT: entry_price is the OPTION PREMIUM, NOT the underlying!
        """
        # Get the correct premium
        premium = self.get_option_premium(underlying_price, strike, option_type)
        
        # Calculate deployed capital (premium × quantity)
        lot_size = self.lot_sizes.get(symbol, 65)
        quantity = lots * lot_size
        deployed = premium * quantity
        
        # Check capital
        if deployed > self.capital * 0.8:  # Max 80% of capital
            max_lots = int((self.capital * 0.8) / (premium * lot_size))
            lots = max(1, max_lots)
            quantity = lots * lot_size
            deployed = premium * quantity
            logger.warning(f"Reduced to {lots} lot(s) due to capital limit")
        
        # Calculate targets (based on premium)
        target1_premium = premium * 1.15  # 15% profit
        target2_premium = premium * 1.30  # 30% profit  
        target3_premium = premium * 1.50  # 50% profit
        stop_premium = premium * 0.95      # 5% loss
        
        trade = {
            "id": f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "symbol": symbol,
            "option_type": option_type,
            "strike": strike,
            "lots": lots,
            "lot_size": lot_size,
            "quantity": quantity,
            # CRITICAL: Store PREMIUM, not underlying!
            "entry_premium": premium,
            "entry_price": premium,  # For compatibility
            "underlying_price": underlying_price,  # Store underlying separately for reference
            "entry_timestamp": datetime.now().isoformat(),
            "status": "OPEN",
            "entry_reason": reason,
            "regime": regime,
            "deployed_capital": deployed,
            # Targets based on premium
            "target1_premium": target1_premium,
            "target1_price": target1_premium,  # For compatibility
            "target2_premium": target2_premium,
            "target2_price": target2_premium,
            "target3_premium": target3_premium,
            "target3_price": target3_premium,
            "stop_premium": stop_premium,
            "stop_loss": stop_premium,
            "confidence": 0.5,
            "hold_count": 0
        }
        
        logger.info(f"[ENTER] {symbol} {option_type} @ ₹{premium:.2f} premium (Underlying: {underlying_price})")
        logger.info(f"[COST] {lots} lots × {lot_size} = {quantity} shares | Deployed: ₹{deployed:,.2f}")
        logger.info(f"[TARGETS] T1: ₹{target1_premium:.2f}, T2: ₹{target2_premium:.2f}, T3: ₹{target3_premium:.2f}")
        
        return trade
    
    def update_position_pnl(self, position: Dict[str, Any], current_underlying: float) -> Dict[str, Any]:
        """
        Update position P&L based on premium changes.
        """
        entry_premium = position.get("entry_premium", position.get("entry_price", 0))
        quantity = position.get("quantity", 0)
        symbol = position.get("symbol", "NIFTY")
        
        # Get current premium (in production, call API)
        # For testing, approximate premium from underlying
        strike = position.get("strike", 0)
        current_premium = self.get_option_premium(current_underlying, strike, position.get("option_type", "CALL"))
        
        # Calculate P&L
        pnl = (current_premium - entry_premium) * quantity
        pnl_percent = ((current_premium / entry_premium) - 1) * 100 if entry_premium > 0 else 0
        
        position["current_premium"] = current_premium
        position["current_price"] = current_premium  # For compatibility
        position["current_underlying"] = current_underlying
        position["pnl"] = pnl
        position["pnl_percent"] = pnl_percent
        position["current_value"] = current_premium * quantity
        position["hold_count"] = position.get("hold_count", 0) + 1
        
        return position
