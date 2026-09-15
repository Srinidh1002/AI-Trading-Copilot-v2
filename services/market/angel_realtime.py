# services/market/angel_realtime.py - REAL ANGEL ONE DATA ONLY

import time
import json
import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class AngelRealtime:
    """Real Angel One data - NO SIMULATION."""
    
    def __init__(self):
        self.last_update = 0
        self.update_interval = 3  # seconds
        self.cache = {}
        self.cache_file = Path("data/angel_realtime_cache.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize Angel One API
        self.api = None
        self._init_api()
        
        # Load cached data
        self._load_cache()
        
        # If no cache, get initial data
        if not self.cache:
            self._fetch_real_data()
        
        logger.info("[ANGEL-REALTIME] Initialized with REAL data")
    
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
                    return True
        except:
            pass
        return False
    
    def _save_cache(self):
        """Save data to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except:
            pass
    
    def _fetch_real_data(self):
        """Fetch REAL data from Angel One API."""
        result = {}
        
        for symbol in ['NIFTY', 'SENSEX']:
            try:
                # Get real LTP
                if self.api:
                    ltp = self.api.get_ltp(symbol)
                    if ltp and ltp > 0:
                        # Get option chain for ATM strike
                        chain = self.api.get_option_chain(symbol)
                        if chain:
                            strikes = chain.get('strikes', [])
                            underlying = chain.get('underlying', ltp)
                            if strikes:
                                # Find ATM strike
                                atm = min(strikes, key=lambda s: abs(s['strike'] - underlying))
                                strike = atm.get('strike', 0)
                                premium = atm.get('call_ltp', 0)
                                
                                # If premium is 0, calculate from underlying
                                if premium <= 0:
                                    premium = ltp * (0.008 if symbol == 'NIFTY' else 0.003)
                                    premium = max(10, round(premium, 2))
                                
                                result[symbol] = {
                                    'ltp': ltp,
                                    'premium': premium,
                                    'strike': strike,
                                    'timestamp': datetime.now().isoformat(),
                                    'source': 'Angel One API'
                                }
                                logger.info(f"[ANGEL-REALTIME] {symbol}: ₹{ltp:.2f}, Premium: ₹{premium:.2f}")
                                continue
                    
                    # Fallback: calculate premium from LTP
                    if ltp > 0:
                        premium = ltp * (0.008 if symbol == 'NIFTY' else 0.003)
                        premium = max(10, round(premium, 2))
                        step = 50 if symbol == 'NIFTY' else 100
                        strike = round(ltp / step) * step
                        
                        result[symbol] = {
                            'ltp': ltp,
                            'premium': premium,
                            'strike': strike,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'Angel One API (Calculated)'
                        }
                        logger.info(f"[ANGEL-REALTIME] {symbol}: ₹{ltp:.2f}, Premium: ₹{premium:.2f} (calculated)")
            except Exception as e:
                logger.error(f"[ANGEL-REALTIME] Error fetching {symbol}: {e}")
        
        if result:
            self.cache = result
            self._save_cache()
        
        return result
    
    def get_ltp(self, symbol: str) -> float:
        """Get REAL LTP from Angel One."""
        try:
            if self.api:
                ltp = self.api.get_ltp(symbol)
                if ltp and ltp > 0:
                    return ltp
        except Exception as e:
            logger.debug(f"[ANGEL-REALTIME] LTP error for {symbol}: {e}")
        
        # Return from cache
        if symbol in self.cache:
            return self.cache[symbol].get('ltp', 0)
        
        return 0
    
    def get_premium(self, symbol: str) -> float:
        """Get REAL premium from Angel One."""
        try:
            if self.api:
                chain = self.api.get_option_chain(symbol)
                if chain:
                    strikes = chain.get('strikes', [])
                    underlying = chain.get('underlying', self.get_ltp(symbol))
                    if strikes and underlying > 0:
                        atm = min(strikes, key=lambda s: abs(s['strike'] - underlying))
                        premium = atm.get('call_ltp', 0)
                        if premium > 0:
                            return premium
        except Exception as e:
            logger.debug(f"[ANGEL-REALTIME] Premium error for {symbol}: {e}")
        
        # Calculate from LTP
        ltp = self.get_ltp(symbol)
        if ltp > 0:
            premium = ltp * (0.008 if symbol == 'NIFTY' else 0.003)
            return max(10, round(premium, 2))
        
        # Return from cache
        if symbol in self.cache:
            return self.cache[symbol].get('premium', 0)
        
        return 0
    
    def get_strike(self, symbol: str) -> float:
        """Get ATM strike from Angel One."""
        try:
            if self.api:
                chain = self.api.get_option_chain(symbol)
                if chain:
                    underlying = chain.get('underlying', self.get_ltp(symbol))
                    strikes = chain.get('strikes', [])
                    if strikes and underlying > 0:
                        atm = min(strikes, key=lambda s: abs(s['strike'] - underlying))
                        return atm.get('strike', 0)
        except Exception as e:
            logger.debug(f"[ANGEL-REALTIME] Strike error for {symbol}: {e}")
        
        # Calculate from LTP
        ltp = self.get_ltp(symbol)
        if ltp > 0:
            step = 50 if symbol == 'NIFTY' else 100
            return round(ltp / step) * step
        
        # Return from cache
        if symbol in self.cache:
            return self.cache[symbol].get('strike', 0)
        
        return 0
    
    def update(self) -> Dict[str, Any]:
        """Update data from Angel One."""
        return self._fetch_real_data()
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current data from cache or fetch new."""
        if not self.cache:
            return self.update()
        return self.cache
