# run_trading_fixed_v2.py - FIXED VERSION WITH PROPER FALLBACK

import asyncio
import logging
import sys
import os
import json
import random
from pathlib import Path
from datetime import datetime
import pytz
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.angel_one_api_fixed import AngelOneAPIFixed
from services.market.websocket_bridge import WebSocketBridge
from services.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class FixedTradingEngineV2:
    """Trading engine with proper fallback for Angel One API."""
    
    def __init__(self, capital: float = 1000000):
        self.capital = capital
        self.positions = {}
        self.active_symbols = set()
        self.is_running = False
        self.cycle_count = 0
        
        # Trading params
        self.T1 = 0.15
        self.T2 = 0.30
        self.T3 = 0.50
        self.stop_loss_pct = 0.05
        self.max_positions = 2
        
        # Lot sizes
        self.lot_sizes = {'NIFTY': 65, 'SENSEX': 20}
        
        # Stats
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'today_trades': 0,
            'target_hits': {'T1': 0, 'T2': 0, 'T3': 0}
        }
        
        # Base prices (will be updated from real data)
        self.base_prices = {
            'NIFTY': 24461.3,
            'SENSEX': 78180.31
        }
        
        # Initialize WebSocket bridge FIRST (as fallback)
        logger.info("[INIT] Initializing WebSocket Bridge...")
        self.bridge = WebSocketBridge('data/task9/live_stream')
        self.bridge.initialize()
        
        # Then try Angel One
        logger.info("[INIT] Initializing Angel One API...")
        self.angel_api = AngelOneAPIFixed()
        
        if self.angel_api.authenticate():
            logger.info("[ANGEL] ✅ Connected successfully!")
            self.use_angel = True
        else:
            logger.warning("[ANGEL] ❌ Connection failed. Using WebSocket fallback.")
            self.use_angel = False
        
        # Get initial market data
        self._refresh_market_data()
        
        logger.info("=" * 60)
        logger.info("[INIT] FIXED TRADING ENGINE V2")
        logger.info(f"[DATA SOURCE] {'Angel One API' if self.use_angel else 'WebSocket Fallback'}")
        logger.info(f"[CAPITAL] ₹{capital:,.2f}")
        logger.info(f"[TARGETS] T1: +{self.T1*100}%, T2: +{self.T2*100}%, T3: +{self.T3*100}%")
        logger.info("=" * 60)
    
    def _refresh_market_data(self):
        """Refresh market data from all sources."""
        # Try Angel One first
        if self.use_angel:
            for symbol in ['NIFTY', 'SENSEX']:
                try:
                    ltp = self.angel_api.get_ltp(symbol)
                    if ltp and ltp > 0:
                        self.base_prices[symbol] = ltp
                        logger.debug(f"[DATA] {symbol}: ₹{ltp:,.2f} (from Angel One)")
                except Exception as e:
                    logger.debug(f"[ANGEL] LTP error for {symbol}: {e}")
        
        # Always update from WebSocket as fallback
        try:
            ws_data = self.bridge.get_latest_data()
            for symbol in ['NIFTY', 'SENSEX']:
                if symbol in ws_data and ws_data[symbol].get('ltp', 0) > 0:
                    ltp = ws_data[symbol]['ltp']
                    self.base_prices[symbol] = ltp
                    logger.debug(f"[DATA] {symbol}: ₹{ltp:,.2f} (from WebSocket)")
        except Exception as e:
            logger.debug(f"[WS] Data error: {e}")
    
    def get_ltp(self, symbol: str) -> float:
        """Get LTP from any available source."""
        # Try Angel One if available
        if self.use_angel:
            try:
                ltp = self.angel_api.get_ltp(symbol)
                if ltp and ltp > 0:
                    self.base_prices[symbol] = ltp
                    return ltp
            except Exception as e:
                logger.debug(f"[ANGEL] LTP error: {e}")
        
        # Try WebSocket bridge
        try:
            ws_data = self.bridge.get_latest_data()
            if symbol in ws_data and ws_data[symbol].get('ltp', 0) > 0:
                ltp = ws_data[symbol]['ltp']
                self.base_prices[symbol] = ltp
                return ltp
        except Exception as e:
            logger.debug(f"[WS] LTP error: {e}")
        
        # Return cached base price
        return self.base_prices.get(symbol, 24461.3 if symbol == 'NIFTY' else 78180.31)
    
    def get_option_chain(self, symbol: str) -> dict:
        """Get option chain from Angel One or generate simulated."""
        if self.use_angel:
            try:
                chain = self.angel_api.get_option_chain(symbol)
                if chain and chain.get('strikes'):
                    return chain
            except Exception as e:
                logger.debug(f"[ANGEL] Option chain error: {e}")
        
        # Generate simulated chain
        return self._generate_simulated_chain(symbol)
    
    def _generate_simulated_chain(self, symbol: str) -> dict:
        """Generate simulated option chain based on current LTP."""
        underlying = self.get_ltp(symbol)
        
        strikes = []
        step = 50 if symbol == 'NIFTY' else 100
        atm_strike = round(underlying / step) * step
        
        for offset in range(-5, 6):
            strike = atm_strike + (offset * step)
            atm_premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
            distance_pct = abs(strike - underlying) / underlying
            
            call_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
            put_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
            
            if strike < underlying:
                call_premium *= 1 + distance_pct * 2
                put_premium *= max(0.1, 1 - distance_pct * 2)
            else:
                call_premium *= max(0.1, 1 - distance_pct * 2)
                put_premium *= 1 + distance_pct * 2
            
            oi_factor = max(0.1, 1 - distance_pct * 10)
            call_oi = int(100000 * oi_factor * (0.5 + offset / 20))
            put_oi = int(100000 * oi_factor * (0.5 - offset / 20))
            
            strikes.append({
                'strike': strike,
                'call_ltp': round(max(5, call_premium), 2),
                'call_oi': max(1000, call_oi),
                'call_oi_change': round(offset * 10, 2),
                'call_volume': max(100, call_oi // 10),
                'put_ltp': round(max(5, put_premium), 2),
                'put_oi': max(1000, put_oi),
                'put_oi_change': round(-offset * 10, 2),
                'put_volume': max(100, put_oi // 10),
                'pcr': max(0.1, put_oi / call_oi if call_oi > 0 else 1)
            })
        
        total_call_oi = sum(s['call_oi'] for s in strikes)
        total_put_oi = sum(s['put_oi'] for s in strikes)
        
        return {
            'symbol': symbol,
            'underlying': underlying,
            'strikes': strikes,
            'total_pcr': total_put_oi / total_call_oi if total_call_oi > 0 else 0.5,
            'simulated': True
        }
    
    def get_best_strike(self, symbol: str, option_type: str = 'CALL') -> dict:
        """Get best strike from option chain."""
        chain = self.get_option_chain(symbol)
        strikes = chain.get('strikes', [])
        underlying = chain.get('underlying', self.get_ltp(symbol))
        
        if not strikes:
            step = 50 if symbol == 'NIFTY' else 100
            strike = round(underlying / step) * step
            premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
            return {'strike': strike, 'premium': premium, 'score': 0.5}
        
        best = None
        best_score = -999
        
        for s in strikes:
            strike = s['strike']
            premium = s.get('call_ltp' if option_type == 'CALL' else 'put_ltp', 0)
            
            if premium <= 0:
                continue
            
            # Scoring
            oi = s.get('call_oi' if option_type == 'CALL' else 'put_oi', 0)
            oi_score = min(1, oi / 1000000) if oi > 0 else 0
            
            atm_distance = abs(strike - underlying)
            atm_score = 1 - min(1, atm_distance / (underlying * 0.02))
            
            # Premium affordability
            ideal_premium = 100 if symbol == 'NIFTY' else 300
            premium_score = 1 - min(0.5, abs(premium - ideal_premium) / ideal_premium)
            
            score = (oi_score * 0.4) + (atm_score * 0.4) + (premium_score * 0.2)
            
            if score > best_score:
                best_score = score
                best = {'strike': strike, 'premium': premium, 'score': score}
        
        if not best:
            step = 50 if symbol == 'NIFTY' else 100
            strike = round(underlying / step) * step
            premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
            best = {'strike': strike, 'premium': premium, 'score': 0.5}
        
        return best
    
    def enter_trade(self, symbol: str) -> Optional[Dict]:
        """Enter a trade."""
        if symbol in self.active_symbols:
            return None
        
        underlying = self.get_ltp(symbol)
        if underlying <= 0:
            return None
        
        # Get best strike
        strike_info = self.get_best_strike(symbol, 'CALL')
        strike = strike_info['strike']
        premium = strike_info['premium']
        
        if premium <= 0:
            return None
        
        lot_size = self.lot_sizes.get(symbol, 65)
        quantity = lot_size
        deployed = premium * quantity
        
        position = {
            'id': f"{symbol}_{datetime.now().strftime('%H%M%S')}",
            'symbol': symbol,
            'strike': strike,
            'option_type': 'CALL',
            'entry_premium': premium,
            'entry_underlying': underlying,
            'entry_time': datetime.now().isoformat(),
            'quantity': quantity,
            'deployed_capital': deployed,
            'target1': premium * (1 + self.T1),
            'target2': premium * (1 + self.T2),
            'target3': premium * (1 + self.T3),
            'stop_loss': premium * (1 - self.stop_loss_pct),
            'status': 'OPEN',
            'current_premium': premium,
            'pnl': 0,
            'pnl_percent': 0,
            'hold_count': 0
        }
        
        self.positions[symbol] = position
        self.active_symbols.add(symbol)
        self.stats['total_trades'] += 1
        self.stats['today_trades'] += 1
        
        logger.info("=" * 50)
        logger.info(f"✅ [TRADE] {symbol} CALL")
        logger.info(f"   Underlying: ₹{underlying:,.2f}")
        logger.info(f"   Strike: {strike}")
        logger.info(f"   Premium: ₹{premium:.2f}")
        logger.info(f"   Deployed: ₹{deployed:,.2f}")
        logger.info(f"   Targets: T1 ₹{position['target1']:.2f}, T2 ₹{position['target2']:.2f}, T3 ₹{position['target3']:.2f}")
        logger.info(f"   Stop Loss: ₹{position['stop_loss']:.2f}")
        logger.info("=" * 50)
        
        return position
    
    def update_positions(self):
        """Update positions with current prices."""
        for symbol, pos in list(self.positions.items()):
            if pos['status'] != 'OPEN':
                continue
            
            underlying = self.get_ltp(symbol)
            if underlying <= 0:
                continue
            
            # Get current premium from option chain
            chain = self.get_option_chain(symbol)
            strikes = chain.get('strikes', [])
            
            current_premium = pos['current_premium']
            for s in strikes:
                if s['strike'] == pos['strike']:
                    current_premium = s.get('call_ltp' if pos['option_type'] == 'CALL' else 'put_ltp', pos['current_premium'])
                    break
            
            pos['current_premium'] = current_premium
            pos['current_underlying'] = underlying
            pos['hold_count'] += 1
            
            pnl = (current_premium - pos['entry_premium']) * pos['quantity']
            pnl_percent = ((current_premium / pos['entry_premium']) - 1) * 100
            pos['pnl'] = pnl
            pos['pnl_percent'] = pnl_percent
            
            # Check targets
            if pnl_percent >= self.T1 * 100 and pos['status'] == 'OPEN':
                pos['status'] = 'TARGET1'
                self.stats['target_hits']['T1'] += 1
                self.stats['winning_trades'] += 1
                logger.info(f"🎯 [T1] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                
            elif pnl_percent >= self.T2 * 100 and pos['status'] == 'TARGET1':
                pos['status'] = 'TARGET2'
                self.stats['target_hits']['T2'] += 1
                logger.info(f"🎯 [T2] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                
            elif pnl_percent >= self.T3 * 100 and pos['status'] == 'TARGET2':
                pos['status'] = 'TARGET3'
                self.stats['target_hits']['T3'] += 1
                logger.info(f"🎯 [T3] {symbol}: +{pnl_percent:.1f}% (₹{pnl:,.2f})")
                self.close_position(symbol, "TARGET3")
                
            elif pnl_percent <= -self.stop_loss_pct * 100:
                pos['status'] = 'STOPPED'
                self.stats['losing_trades'] += 1
                logger.info(f"⛔ [STOP] {symbol}: {pnl_percent:.1f}% (₹{pnl:,.2f})")
                self.close_position(symbol, "STOP_LOSS")
    
    def close_position(self, symbol: str, reason: str):
        """Close a position."""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        pos['status'] = 'COMPLETED'
        pos['exit_time'] = datetime.now().isoformat()
        pos['exit_reason'] = reason
        self.stats['total_pnl'] += pos['pnl']
        self.active_symbols.discard(symbol)
        
        logger.info(f"[CLOSE] {symbol}: {reason} | P&L: {pos['pnl_percent']:+.1f}% (₹{pos['pnl']:,.2f})")
    
    async def run_trading_loop(self):
        """Main trading loop."""
        logger.info("=" * 60)
        logger.info("📊 TRADING LOOP - ACTIVE")
        logger.info("=" * 60)
        
        while self.is_running:
            try:
                self.cycle_count += 1
                
                # Refresh market data periodically
                if self.cycle_count % 5 == 0:
                    self._refresh_market_data()
                
                # Update positions
                self.update_positions()
                
                # Enter new trades
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol in self.active_symbols:
                        continue
                    if len(self.active_symbols) >= self.max_positions:
                        break
                    
                    underlying = self.get_ltp(symbol)
                    if underlying > 0:
                        self.enter_trade(symbol)
                
                # Status update
                if self.cycle_count % 10 == 0:
                    deployed = sum(p['deployed_capital'] for p in self.positions.values() if p['status'] == 'OPEN')
                    logger.info(f"📊 [STATUS] Cycle {self.cycle_count}: {len(self.active_symbols)} active, Deployed: ₹{deployed:,.2f}")
                    
                    for symbol in ['NIFTY', 'SENSEX']:
                        ltp = self.get_ltp(symbol)
                        if ltp > 0:
                            logger.info(f"   {symbol}: ₹{ltp:,.2f}")
                
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                await asyncio.sleep(5)
    
    async def start(self):
        """Start the engine."""
        logger.info("🚀 STARTING FIXED TRADING ENGINE V2")
        self.is_running = True
        await self.run_trading_loop()


async def main():
    engine = FixedTradingEngineV2(capital=1000000)
    await engine.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted")
