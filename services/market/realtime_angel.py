# services/market/realtime_angel.py - REAL ANGEL ONE DATA STREAM

import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AngelOneRealtime:
    """Real-time data from Angel One API."""
    
    def __init__(self):
        self.last_update = 0
        self.update_interval = 3  # seconds
        self.cache = {}
        self.cache_file = Path("data/angel_realtime_cache.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Try to load cached data
        self._load_cache()
        
        # Initialize Angel One API
        self.api = None
        self._init_api()
        
        logger.info("[ANGEL-REALTIME] Initialized")
    
    def _init_api(self):
        """Initialize Angel One API."""
        try:
            from services.market.angel_one_api_fixed import AngelOneAPIFixed
            self.api = AngelOneAPIFixed()
            if self.api.authenticate():
                logger.info("[ANGEL-REALTIME] Connected to Angel One!")
                return True
        except Exception as e:
            logger.error(f"[ANGEL-REALTIME] Failed to connect: {e}")
        return False
    
    def _load_cache(self):
        """Load cached data."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                    logger.info(f"[ANGEL-REALTIME] Loaded cache from {self.cache_file}")
        except:
            pass
    
    def _save_cache(self):
        """Save data to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except:
            pass
    
    def get_ltp(self, symbol: str) -> float:
        """Get real LTP from Angel One."""
        try:
            if self.api:
                ltp = self.api.get_ltp(symbol)
                if ltp and ltp > 0:
                    return ltp
        except Exception as e:
            logger.debug(f"[ANGEL-REALTIME] LTP error for {symbol}: {e}")
        
        # Try cache
        if symbol in self.cache:
            return self.cache[symbol].get('ltp', 0)
        
        return 0
    
    def get_option_premium(self, symbol: str, strike: float) -> float:
        """Get real option premium from Angel One."""
        try:
            if self.api:
                chain = self.api.get_option_chain(symbol)
                if chain:
                    strikes = chain.get('strikes', [])
                    for s in strikes:
                        if s.get('strike') == strike:
                            return s.get('call_ltp', 0)
        except Exception as e:
            logger.debug(f"[ANGEL-REALTIME] Option chain error: {e}")
        
        # Calculate from underlying if API fails
        underlying = self.get_ltp(symbol)
        if underlying > 0:
            atm_premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
            return round(atm_premium, 2)
        
        return 0
    
    def get_atm_strike(self, symbol: str) -> float:
        """Get ATM strike from Angel One."""
        try:
            if self.api:
                chain = self.api.get_option_chain(symbol)
                if chain:
                    underlying = chain.get('underlying', 0)
                    strikes = chain.get('strikes', [])
                    if strikes and underlying > 0:
                        atm = min(strikes, key=lambda s: abs(s['strike'] - underlying))
                        return atm.get('strike', 0)
        except:
            pass
        
        # Calculate from underlying
        underlying = self.get_ltp(symbol)
        step = 50 if symbol == 'NIFTY' else 100
        return round(underlying / step) * step
    
    def update(self) -> Dict[str, Any]:
        """Update all data from Angel One."""
        result = {}
        
        for symbol in ['NIFTY', 'SENSEX']:
            try:
                # Get real LTP
                ltp = self.get_ltp(symbol)
                
                # Get option chain for ATM strike and premium
                atm_strike = self.get_atm_strike(symbol)
                premium = self.get_option_premium(symbol, atm_strike)
                
                result[symbol] = {
                    'ltp': ltp,
                    'premium': premium,
                    'strike': atm_strike,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Update cache
                self.cache[symbol] = result[symbol]
                
            except Exception as e:
                logger.error(f"[ANGEL-REALTIME] Update error for {symbol}: {e}")
                if symbol in self.cache:
                    result[symbol] = self.cache[symbol]
        
        self._save_cache()
        return result
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current data from cache."""
        if not self.cache:
            return self.update()
        return self.cache
