# services/market/websocket_bridge_unified.py
# UNIFIED WEBSOCKET BRIDGE - Integrates Angel One data

import json
import logging
import asyncio
import random
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class AngelOneAPI:
    """Angel One API integration for real market data."""
    
    def __init__(self, api_key: str = None, client_id: str = None):
        self.api_key = api_key
        self.client_id = client_id
        self.base_url = "https://apiconnect.angelone.in"
        self.session_token = None
        self.feed_token = None
    
    def get_option_chain(self, symbol: str, expiry: str = None) -> dict:
        """
        Get option chain data from Angel One.
        
        In production, this would call the Angel One API.
        For now, returns mock data based on the Angel One screenshots.
        """
        # Mock data based on the Angel One TradeOne screenshot
        if symbol == 'NIFTY':
            return {
                'underlying': 24461.3,
                'strikes': [
                    {'strike': 23650, 'call_ltp': 356.15, 'call_oi': 154000, 'call_oi_change': 20.35, 'call_volume': 147800, 
                     'put_ltp': 15.60, 'put_oi': 4538000, 'put_oi_change': 66.96, 'put_volume': 1700000, 'pcr': 0.52},
                    {'strike': 23700, 'call_ltp': 310.00, 'call_oi': 669000, 'call_oi_change': 9.21, 'call_volume': 239640,
                     'put_ltp': 20.75, 'put_oi': 8555000, 'put_oi_change': 42.66, 'put_volume': 3110000, 'pcr': 0.56},
                    {'strike': 23750, 'call_ltp': 267.20, 'call_oi': 610000, 'call_oi_change': 43.52, 'call_volume': 46010,
                     'put_ltp': 27.55, 'put_oi': 5424000, 'put_oi_change': 101.50, 'put_volume': 2250000, 'pcr': 0.57},
                    {'strike': 23800, 'call_ltp': 225.90, 'call_oi': 3663000, 'call_oi_change': 30.37, 'call_volume': 184040,
                     'put_ltp': 36.95, 'put_oi': 14000000, 'put_oi_change': 95.00, 'put_volume': 4600000, 'pcr': 0.64},
                    {'strike': 23850, 'call_ltp': 188.00, 'call_oi': 2537000, 'call_oi_change': 41.15, 'call_volume': 330750,
                     'put_ltp': 48.35, 'put_oi': 9151000, 'put_oi_change': 147.77, 'put_volume': 3640000, 'pcr': 0.72},
                    {'strike': 23900, 'call_ltp': 152.85, 'call_oi': 11100000, 'call_oi_change': 43.07, 'call_volume': 82990,
                     'put_ltp': 63.45, 'put_oi': 21500000, 'put_oi_change': 209.21, 'put_volume': 9140000, 'pcr': 0.85},
                    {'strike': 23950, 'call_ltp': 121.25, 'call_oi': 10500000, 'call_oi_change': 78.33, 'call_volume': 22570,
                     'put_ltp': 82.15, 'put_oi': 8873000, 'put_oi_change': 322.64, 'put_volume': 5630000, 'pcr': 0.95},
                    {'strike': 24000, 'call_ltp': 93.90, 'call_oi': 22000000, 'call_oi_change': 19.57, 'call_volume': 315100,
                     'put_ltp': 104.80, 'put_oi': 12100000, 'put_oi_change': 64.13, 'put_volume': 4280000, 'pcr': 0.98},
                    {'strike': 24050, 'call_ltp': 70.75, 'call_oi': 9925000, 'call_oi_change': 27.37, 'call_volume': 76540,
                     'put_ltp': 131.80, 'put_oi': 2686000, 'put_oi_change': 141.27, 'put_volume': 1130000, 'pcr': 1.05},
                    {'strike': 24100, 'call_ltp': 52.10, 'call_oi': 14400000, 'call_oi_change': 18.64, 'call_volume': 234880,
                     'put_ltp': 162.85, 'put_oi': 4540000, 'put_oi_change': 36.54, 'put_volume': 1110000, 'pcr': 1.08},
                    {'strike': 24150, 'call_ltp': 37.35, 'call_oi': 7194000, 'call_oi_change': 38.18, 'call_volume': 365950,
                     'put_ltp': 198.40, 'put_oi': 1053000, 'put_oi_change': 48.10, 'put_volume': 217900, 'pcr': 1.12},
                    {'strike': 24200, 'call_ltp': 26.50, 'call_oi': 14500000, 'call_oi_change': 22.72, 'call_volume': 113520,
                     'put_ltp': 237.60, 'put_oi': 2985000, 'put_oi_change': 13.93, 'put_volume': 311100, 'pcr': 1.15},
                ],
                'pcr': 0.95,
                'max_oi_call': 24000,
                'max_oi_put': 23800,
                'vix': 11.34
            }
        elif symbol == 'SENSEX':
            return {
                'underlying': 78180.31,
                'strikes': [
                    {'strike': 76000, 'call_ltp': 986.25, 'call_oi': 2700, 'call_oi_change': 3.68, 'call_volume': 1620,
                     'put_ltp': 160.00, 'put_oi': 603000, 'put_oi_change': 121.92, 'put_volume': 205000, 'pcr': 0.25},
                    {'strike': 76100, 'call_ltp': 904.30, 'call_oi': 17100, 'call_oi_change': -10.73, 'call_volume': 5690,
                     'put_ltp': 182.40, 'put_oi': 213000, 'put_oi_change': 294.81, 'put_volume': 94300, 'pcr': 0.32},
                    {'strike': 76200, 'call_ltp': 834.55, 'call_oi': 37800, 'call_oi_change': 13.52, 'call_volume': 2160,
                     'put_ltp': 207.35, 'put_oi': 398000, 'put_oi_change': 552.43, 'put_volume': 139900, 'pcr': 0.35},
                    {'strike': 76300, 'call_ltp': 761.65, 'call_oi': 45600, 'call_oi_change': 40.27, 'call_volume': 2290,
                     'put_ltp': 234.75, 'put_oi': 258000, 'put_oi_change': 321.54, 'put_volume': 123100, 'pcr': 0.38},
                    {'strike': 76400, 'call_ltp': 692.30, 'call_oi': 61600, 'call_oi_change': 62.76, 'call_volume': 3240,
                     'put_ltp': 265.30, 'put_oi': 377000, 'put_oi_change': 537.70, 'put_volume': 151300, 'pcr': 0.42},
                    {'strike': 76500, 'call_ltp': 628.35, 'call_oi': 465000, 'call_oi_change': 30.02, 'call_volume': 18070,
                     'put_ltp': 298.35, 'put_oi': 1066000, 'put_oi_change': 222.59, 'put_volume': 418700, 'pcr': 0.48},
                    {'strike': 76600, 'call_ltp': 565.00, 'call_oi': 514000, 'call_oi_change': 175.33, 'call_volume': 27870,
                     'put_ltp': 335.90, 'put_oi': 789000, 'put_oi_change': 783.01, 'put_volume': 403300, 'pcr': 0.55},
                    {'strike': 76700, 'call_ltp': 504.30, 'call_oi': 453000, 'call_oi_change': 360.44, 'call_volume': 26970,
                     'put_ltp': 376.55, 'put_oi': 721000, 'put_oi_change': 677.61, 'put_volume': 337700, 'pcr': 0.62},
                    {'strike': 76800, 'call_ltp': 449.70, 'call_oi': 455000, 'call_oi_change': 84.57, 'call_volume': 21610,
                     'put_ltp': 419.95, 'put_oi': 369000, 'put_oi_change': 279.84, 'put_volume': 147500, 'pcr': 0.68},
                    {'strike': 76900, 'call_ltp': 397.90, 'call_oi': 267000, 'call_oi_change': 190.83, 'call_volume': 15970,
                     'put_ltp': 467.40, 'put_oi': 175000, 'put_oi_change': 174.28, 'put_volume': 72300, 'pcr': 0.75},
                    {'strike': 77000, 'call_ltp': 351.25, 'call_oi': 1004000, 'call_oi_change': 82.08, 'call_volume': 30670,
                     'put_ltp': 520.30, 'put_oi': 514000, 'put_oi_change': 74.86, 'put_volume': 109800, 'pcr': 0.82},
                ],
                'pcr': 0.68,
                'max_oi_call': 77000,
                'max_oi_put': 76500,
                'vix': 11.34
            }
        return None


class UnifiedWebSocketBridge:
    """Unified WebSocket Bridge with Angel One integration."""
    
    def __init__(self, data_dir: str = "data/task9/live_stream"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.subscribers = []
        self.latest_data = {}
        self.option_chain_data = {}
        self.is_running = False
        self.symbols = ['NIFTY', 'SENSEX']
        self.base_prices = {'NIFTY': 24461.3, 'SENSEX': 78180.31}
        self.synthetic_mode = False
        self.angel_one = AngelOneAPI()
        
        logger.info("[BRIDGE] Unified WebSocket Bridge initialized")
    
    def initialize(self):
        """Initialize the bridge."""
        logger.info(f"[BRIDGE] Monitoring: {self.data_dir}")
        self.is_running = True
        
        # Load data
        loaded = self._load_data()
        
        if not loaded:
            logger.warning("[BRIDGE] No data loaded. Using synthetic + Angel One mock data.")
            self.synthetic_mode = True
            self._generate_data()
        
        # Start polling
        asyncio.create_task(self._poll_data())
        return self
    
    def _load_data(self) -> bool:
        """Load data from files."""
        loaded = False
        locations = [
            self.data_dir,
            Path("data/paper_trading/certified_runtime/task9/live_stream"),
        ]
        
        for loc in locations:
            if loc.exists():
                files = sorted(loc.glob("*.json*"), key=lambda x: x.stat().st_mtime, reverse=True)
                for file_path in files[:5]:
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            if content.strip():
                                self._parse_data(content)
                                loaded = True
                    except Exception as e:
                        pass
        
        # Also load Angel One mock data
        self._load_angelone_data()
        return loaded
    
    def _load_angelone_data(self):
        """Load Angel One option chain data."""
        for symbol in self.symbols:
            option_chain = self.angel_one.get_option_chain(symbol)
            if option_chain:
                self.option_chain_data[symbol] = option_chain
                logger.info(f"[BRIDGE] Loaded Angel One data for {symbol}")
    
    def _parse_data(self, content: str):
        """Parse various data formats."""
        try:
            data = json.loads(content)
            if isinstance(data, dict) and "ticks" in data:
                for tick in data.get("ticks", []):
                    self._process_tick(tick)
            elif isinstance(data, list):
                for tick in data:
                    self._process_tick(tick)
        except json.JSONDecodeError:
            lines = content.strip().split('\n')
            for line in lines:
                try:
                    tick = json.loads(line)
                    self._process_tick(tick)
                except:
                    pass
    
    def _process_tick(self, tick: dict):
        """Process a tick."""
        try:
            symbol = tick.get('market', tick.get('symbol', ''))
            if symbol in self.symbols:
                ltp = tick.get('ltp', 0)
                if ltp > 0:
                    self.latest_data[symbol] = {
                        'ltp': ltp,
                        'timestamp': tick.get('timestamp', datetime.now().isoformat())
                    }
                    
                    # Also update base prices
                    self.base_prices[symbol] = ltp
        except:
            pass
    
    def _generate_data(self):
        """Generate synthetic data with Angel One structure."""
        for symbol in self.symbols:
            base = self.base_prices.get(symbol, 24000)
            
            # Add slight variation
            variation = random.uniform(-0.005, 0.005)
            price = base * (1 + variation)
            
            self.latest_data[symbol] = {
                'ltp': round(price, 2),
                'timestamp': datetime.now().isoformat()
            }
            
            # Generate option chain
            self.option_chain_data[symbol] = self.angel_one.get_option_chain(symbol)
    
    async def _poll_data(self):
        """Poll for new data."""
        while self.is_running:
            try:
                if self.synthetic_mode:
                    # Update prices with random walk
                    for symbol in self.symbols:
                        if symbol in self.latest_data:
                            current = self.latest_data[symbol]['ltp']
                            change = random.uniform(-0.002, 0.002) * current
                            new_price = max(current + change, 20000)
                            self.latest_data[symbol]['ltp'] = round(new_price, 2)
                            self.latest_data[symbol]['timestamp'] = datetime.now().isoformat()
                
                # Notify subscribers
                for callback in self.subscribers:
                    try:
                        callback({
                            'market_data': self.latest_data,
                            'option_chain': self.option_chain_data
                        })
                    except Exception as e:
                        pass
                
                await asyncio.sleep(2)
                
            except Exception as e:
                await asyncio.sleep(5)
    
    def get_latest_data(self) -> dict:
        """Get latest market data."""
        return self.latest_data
    
    def get_option_chain(self, symbol: str) -> dict:
        """Get option chain data for a symbol."""
        return self.option_chain_data.get(symbol, {})
    
    def get_pcr(self, symbol: str) -> float:
        """Get Put-Call Ratio."""
        chain = self.option_chain_data.get(symbol, {})
        return chain.get('pcr', 0.5)
    
    def get_best_strike(self, symbol: str, option_type: str = "CALL") -> dict:
        """
        Get the best strike to trade based on option chain data.
        Uses the actual Angel One data structure.
        """
        chain = self.option_chain_data.get(symbol, {})
        strikes = chain.get('strikes', [])
        underlying = self.latest_data.get(symbol, {}).get('ltp', self.base_prices.get(symbol, 24000))
        
        if not strikes:
            # Fallback to simple calculation
            atm_strike = round(underlying / 50) * 50 if symbol == 'NIFTY' else round(underlying / 100) * 100
            return {'strike': atm_strike, 'premium': self._calc_premium(symbol, atm_strike, option_type)}
        
        best = None
        best_score = -999
        
        for strike_data in strikes:
            strike = strike_data['strike']
            premium = strike_data['call_ltp'] if option_type == 'CALL' else strike_data['put_ltp']
            
            # Scoring
            # 1. OI score - higher OI = better liquidity
            oi = strike_data['call_oi'] if option_type == 'CALL' else strike_data['put_oi']
            oi_score = min(1, oi / 1000000)  # Normalize to 1M
            
            # 2. OI change score - positive = interest
            oi_change = strike_data['call_oi_change'] if option_type == 'CALL' else strike_data['put_oi_change']
            oi_change_score = min(1, max(0, oi_change / 100))
            
            # 3. ATM score - closer to ATM is better
            atm_score = 1 - abs(strike - underlying) / underlying * 0.5
            
            # 4. Premium affordability
            premium_score = 1.0
            if premium < 20:
                premium_score = premium / 20
            elif premium > 500:
                premium_score = 500 / premium
            
            # Total score
            score = (oi_score * 0.3) + (oi_change_score * 0.3) + (atm_score * 0.25) + (premium_score * 0.15)
            
            if score > best_score:
                best_score = score
                best = {
                    'strike': strike,
                    'premium': premium,
                    'oi': oi,
                    'oi_change': oi_change,
                    'score': score,
                    'is_atm': abs(strike - underlying) < 50 if symbol == 'NIFTY' else abs(strike - underlying) < 100
                }
        
        if best:
            logger.info(f"[BRIDGE] Best {symbol} {option_type}: Strike {best['strike']} @ ₹{best['premium']:.2f} (Score: {best['score']:.2f})")
        
        return best
    
    def _calc_premium(self, symbol: str, strike: float, option_type: str) -> float:
        """Calculate premium for a strike."""
        underlying = self.latest_data.get(symbol, {}).get('ltp', self.base_prices.get(symbol, 24000))
        
        if option_type == 'CALL':
            if strike > underlying:
                return max(10, (underlying / strike) * (underlying * 0.008))
            else:
                return max(10, (1 + (underlying - strike) / underlying) * (underlying * 0.008))
        else:  # PUT
            if strike < underlying:
                return max(10, (strike / underlying) * (underlying * 0.008))
            else:
                return max(10, (1 + (strike - underlying) / underlying) * (underlying * 0.008))
    
    def subscribe(self, callback):
        """Subscribe to data updates."""
        self.subscribers.append(callback)
        return len(self.subscribers) - 1
    
    def unsubscribe(self, index):
        """Unsubscribe from data updates."""
        if index < len(self.subscribers):
            self.subscribers.pop(index)
    
    def stop(self):
        """Stop the bridge."""
        self.is_running = False
