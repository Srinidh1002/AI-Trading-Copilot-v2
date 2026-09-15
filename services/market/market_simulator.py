# services/market/market_simulator.py - REALISTIC MARKET SIMULATOR (FIXED)

import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Any, List, Callable

logger = logging.getLogger(__name__)


class MarketSimulator:
    """Realistic market simulator based on actual market data."""
    
    def __init__(self):
        self.subscribers: List[Callable] = []
        self.latest_data: Dict[str, Any] = {}
        self.option_chain: Dict[str, List[Dict]] = {}
        self.is_running = False
        self.tick_count = 0
        
        # ACTUAL market values from Angel One TradeOne (2026-09-04)
        self.base_prices = {
            "NIFTY": 23950.0,
            "SENSEX": 76800.0
        }
        
        self.current_prices = self.base_prices.copy()
        self.volatility = 0.0003
        self.trend = {"NIFTY": 0, "SENSEX": 0}
        self.trend_change_counter = 0
        
        self.lot_sizes = {"NIFTY": 65, "SENSEX": 20}
        self.strike_steps = {"NIFTY": 50, "SENSEX": 100}
        
        logger.info("✅ Market simulator initialized with actual market values")
        logger.info(f"   NIFTY Base: {self.base_prices['NIFTY']:.2f}")
        logger.info(f"   SENSEX Base: {self.base_prices['SENSEX']:.2f}")
    
    def _simulate_price(self, symbol: str) -> float:
        """Simulate realistic price movement."""
        base = self.current_prices.get(symbol, self.base_prices.get(symbol, 0))
        
        self.trend_change_counter += 1
        if self.trend_change_counter > random.randint(3, 6):
            self.trend_change_counter = 0
            self.trend[symbol] = random.uniform(-0.2, 0.2) * self.volatility
        
        if random.random() < 0.3:
            self.trend[symbol] *= 1.2
        
        movement = self.trend[symbol] * base
        noise = random.uniform(-0.5, 0.5) * self.volatility * base
        
        new_price = base + movement + noise
        
        max_deviation = base * 0.01
        if abs(new_price - base) > max_deviation:
            new_price = base + (max_deviation if new_price > base else -max_deviation)
        
        return round(new_price, 2)
    
    def _generate_option_chain(self, symbol: str, ltp: float) -> List[Dict]:
        """Generate realistic option chain."""
        step = self.strike_steps.get(symbol, 50)
        atm = round(ltp / step) * step
        
        chain = []
        for offset in range(-3, 4):
            strike = atm + (offset * step)
            
            if symbol == "NIFTY":
                atm_premium = ltp * 0.0044
            else:
                atm_premium = ltp * 0.0015
            
            if strike > ltp:
                call_premium = atm_premium * max(0.1, 1 - (strike - ltp) / ltp * 2)
            else:
                call_premium = atm_premium * (1 + (ltp - strike) / ltp * 2)
            
            call_premium = max(5, round(call_premium, 2))
            
            chain.append({
                "strike": strike,
                "call_ltp": call_premium,
                "put_ltp": round(call_premium * 0.7, 2),
                "is_atm": strike == atm,
                "offset": offset,
                "moneyness": "ATM" if strike == atm else "OTM" if strike > ltp else "ITM"
            })
        
        return chain
    
    def _get_best_strike(self, symbol: str, chain: List[Dict]) -> Dict:
        """Get best strike from option chain."""
        for strike_data in chain:
            if strike_data.get("is_atm", False):
                return {
                    "strike": strike_data["strike"],
                    "premium": strike_data["call_ltp"],
                    "score": 50,
                    "moneyness": "ATM"
                }
        return {"strike": 0, "premium": 0, "score": 0}
    
    def subscribe(self, callback: Callable) -> int:
        """Subscribe to data updates."""
        self.subscribers.append(callback)
        return len(self.subscribers) - 1
    
    def get_latest(self) -> Dict[str, Any]:
        """Get latest market data."""
        return self.latest_data
    
    def get_option_chain(self, symbol: str) -> List[Dict]:
        """Get option chain."""
        return self.option_chain.get(symbol, [])
    
    async def connect(self):
        """Start streaming."""
        logger.info("🔌 Starting market simulator...")
        self.is_running = True
        asyncio.create_task(self._stream_data())
        return True
    
    async def _stream_data(self):
        """Stream simulated market data."""
        while self.is_running:
            self.tick_count += 1
            
            for symbol in ["NIFTY", "SENSEX"]:
                new_price = self._simulate_price(symbol)
                self.current_prices[symbol] = new_price
                
                self.latest_data[symbol] = {
                    "ltp": new_price,
                    "timestamp": datetime.now().isoformat(),
                    "source": "Market Simulator"
                }
                
                chain = self._generate_option_chain(symbol, new_price)
                self.option_chain[symbol] = chain
                
                best = self._get_best_strike(symbol, chain)
                self.latest_data[symbol]["best_call"] = best
                self.latest_data[symbol]["option_chain"] = chain
                
                for callback in self.subscribers:
                    try:
                        await callback(self.latest_data[symbol])
                    except:
                        pass
                
                if self.tick_count % 5 == 0:
                    logger.info(f"📊 {symbol}: ₹{new_price:,.2f} | Best: {best.get('strike', 0)} @ ₹{best.get('premium', 0):.2f}")
            
            await asyncio.sleep(2)
    
    def stop(self):
        """Stop the simulator."""
        self.is_running = False
        logger.info("🛑 Market simulator stopped")
