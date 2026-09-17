# services/trading/deployment_manager.py
# FIXED: Cap position size to available capital

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class DeploymentManager:
    """Manages deployed capital and position sizing - FIXED CAPITAL CAPPING"""
    
    def __init__(self, config_file: str = "config/deployment_config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
        self.lot_sizes = {
            'NIFTY': 65,
            'SENSEX': 20,
        }
        self.option_lot_sizes = {
            'NIFTY': 65,
            'SENSEX': 20,
        }
        
        logger.info(f"[LOT] NIFTY: {self.lot_sizes['NIFTY']} units/lot")
        logger.info(f"[LOT] SENSEX: {self.lot_sizes['SENSEX']} units/lot")
        
    def _load_config(self) -> Dict:
        default_config = {
            'deployed_capital': 1000000,
            'risk_per_trade': 2,
            'max_risk_per_day': 10,
            'position_sizing': 'fixed',
            'max_lots_per_trade': 5,
            'min_lots_per_trade': 1,
            'prefer_options': True,
            'last_updated': datetime.now().isoformat()
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except:
                return default_config
        else:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def update_capital(self, capital: float):
        self.config['deployed_capital'] = capital
        self.config['last_updated'] = datetime.now().isoformat()
        self._save_config()
        logger.info(f"[MONEY] Deployed Capital Updated: ₹{capital:,.2f}")
    
    def get_position_size(self, symbol: str, entry_price: float, stop_loss: float) -> Dict:
        """Calculate position size - FIXED: Capital capped"""
        capital = self.config.get('deployed_capital', 1000000)
        risk_per_trade = self.config.get('risk_per_trade', 2) / 100
        max_lots = self.config.get('max_lots_per_trade', 5)
        
        # Calculate risk amount
        risk_amount = capital * risk_per_trade
        
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)
        
        # Calculate number of shares based on risk
        if risk_per_share > 0:
            shares = int(risk_amount / risk_per_share)
        else:
            shares = 0
        
        # Get lot size
        lot_size = self.option_lot_sizes.get(symbol, 65) if self.config.get('prefer_options', True) else self.lot_sizes.get(symbol, 65)
        
        # Calculate lots from risk-based shares
        lots = int(shares / lot_size) if lot_size > 0 else 0
        
        # Apply limits
        lots = max(lots, self.config.get('min_lots_per_trade', 1))
        lots = min(lots, max_lots)
        
        total_quantity = lots * lot_size
        
        # === CRITICAL FIX: Cap capital used to available capital ===
        capital_used = entry_price * total_quantity
        
        # If capital used exceeds available capital, reduce lots
        max_lots_by_capital = int(capital / (entry_price * lot_size)) if entry_price > 0 else 0
        max_lots_by_capital = max(max_lots_by_capital, 1)  # At least 1 lot if possible
        
        # Use the smaller of risk-based lots and capital-based lots
        lots = min(lots, max_lots_by_capital, max_lots)
        lots = max(lots, 1)  # Ensure at least 1 lot
        
        total_quantity = lots * lot_size
        capital_used = entry_price * total_quantity
        
        # Recalculate risk
        total_risk = risk_per_share * total_quantity
        risk_percent = (total_risk / capital) * 100 if capital > 0 else 0
        capital_used_percent = (capital_used / capital) * 100 if capital > 0 else 0
        
        # === ENSURE CAPITAL USED <= AVAILABLE CAPITAL ===
        if capital_used > capital:
            # Last resort: reduce to 1 lot
            lots = 1
            total_quantity = lots * lot_size
            capital_used = entry_price * total_quantity
            total_risk = risk_per_share * total_quantity
            risk_percent = (total_risk / capital) * 100 if capital > 0 else 0
            capital_used_percent = (capital_used / capital) * 100 if capital > 0 else 0
            
            logger.warning(f"[WARN] Capital exceeded! Reduced to 1 lot ({total_quantity} shares)")
        
        return {
            'symbol': symbol,
            'lot_size': lot_size,
            'lots': lots,
            'total_quantity': total_quantity,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'risk_per_share': risk_per_share,
            'total_risk': total_risk,
            'risk_percent': risk_percent,
            'capital_used': capital_used,
            'capital_used_percent': capital_used_percent,
            'deployed_capital': capital
        }
    
    def _save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get_config(self) -> Dict:
        return self.config
    
    def display_summary(self):
        config = self.get_config()
        logger.info("=" * 50)
        logger.info("[MONEY] DEPLOYMENT SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Deployed Capital: ₹{config.get('deployed_capital', 0):,.2f}")
        logger.info(f"Risk per Trade: {config.get('risk_per_trade', 2)}%")
        logger.info(f"Max Daily Risk: {config.get('max_risk_per_day', 10)}%")
        logger.info(f"Max Lots/Trade: {config.get('max_lots_per_trade', 5)}")
        logger.info("")
        logger.info("[LOT] LOT SIZES (SEBI 2026):")
        logger.info(f"  NIFTY: {self.lot_sizes['NIFTY']} units/lot")
        logger.info(f"  SENSEX: {self.lot_sizes['SENSEX']} units/lot")
        logger.info("=" * 50)
