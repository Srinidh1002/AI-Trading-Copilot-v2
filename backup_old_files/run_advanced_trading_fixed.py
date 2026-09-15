# run_advanced_trading_fixed.py - Fixed version with proper trade management

import asyncio
import logging
import sys
import os
import json
from pathlib import Path
from datetime import datetime, time, timedelta
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine
from services.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class AdvancedTradingSystem:
    def __init__(self):
        self.engine = None
        self.bridge = None
        self.is_running = False
        self.cycle_count = 0
        self.today_date = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        self.last_trade_time = {}
        self.trade_cooldown = 15  # seconds between trades per symbol
        self.max_positions = 2

    async def start_trading(self):
        """Start the trading engine."""
        logger.info("=" * 70)
        logger.info("🚀 STARTING TRADING ENGINE - FIXED")
        logger.info("=" * 70)
        
        self.bridge = WebSocketBridge('data/task9/live_stream')
        self.bridge.initialize()
        
        self.engine = AdvancedPaperTradingEngine(
            bridge=self.bridge,
            capital=1000000,
            max_positions=self.max_positions
        )
        await self.engine.start()
        
        self.is_running = True
        logger.info(f"[LOT] NIFTY: 65 shares/lot | SENSEX: 20 shares/lot")
        logger.info(f"[TARGETS] T1: +15%, T2: +30%, T3: +50%")
        logger.info(f"[STOP] Stop Loss: -5%")
        logger.info(f"[COOLDOWN] {self.trade_cooldown}s between trades")
        
        await self.run_trading_loop()

    async def run_trading_loop(self):
        """Main trading loop with cooldown."""
        logger.info("=" * 70)
        logger.info("📊 TRADING LOOP - ACTIVE")
        logger.info("=" * 70)
        
        target_hits = {'TARGET1': 0, 'TARGET2': 0, 'TARGET3': 0}
        
        while self.is_running:
            try:
                self.cycle_count += 1
                
                # Get market data
                market_data = {}
                if self.bridge and hasattr(self.bridge, 'get_latest_data'):
                    try:
                        market_data = self.bridge.get_latest_data()
                    except:
                        pass
                
                if not market_data:
                    await asyncio.sleep(2)
                    continue
                
                # Process each symbol
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol not in market_data:
                        continue
                    
                    tick = market_data[symbol]
                    ltp = tick.get('ltp', 0)
                    if ltp <= 0:
                        continue
                    
                    # Check if we already have an open position for this symbol
                    existing_pos = next(
                        (p for p in self.engine.positions 
                         if p.get('symbol') == symbol and p.get('status') == 'OPEN'),
                        None
                    )
                    
                    if existing_pos:
                        # Update position with current price
                        self.engine.update_positions({'symbol': symbol, 'ltp': ltp})
                        continue
                    
                    # Check cooldown
                    last_time = self.last_trade_time.get(symbol, datetime.min)
                    if (datetime.now() - last_time).seconds < self.trade_cooldown:
                        continue
                    
                    # Get premium
                    premium = self.engine.get_option_premium(symbol, ltp, 'CALL')
                    
                    # Check if we can enter a trade
                    open_positions = [p for p in self.engine.positions if p.get('status') == 'OPEN']
                    if len(open_positions) >= self.max_positions:
                        continue
                    
                    # Create and enter trade
                    signal = {
                        'signal': 'TRADE',
                        'symbol': symbol,
                        'option_type': 'CALL',
                        'entry_premium': premium,
                        'lots': 1,
                        'reason': f"{symbol} - Market opportunity",
                        'regime': 'NEUTRAL',
                        'confidence': 0.70
                    }
                    
                    position = self.engine._enter_option_position(
                        {'symbol': symbol, 'ltp': ltp},
                        'CALL',
                        signal,
                        {}
                    )
                    
                    if position:
                        self.last_trade_time[symbol] = datetime.now()
                        logger.info(f"✅ [TRADE] {symbol} CALL @ ₹{position['entry_price']:.2f} premium")
                        logger.info(f"💰 [COST] Deployed: ₹{position['deployed_capital']:,.2f} ({position['deployed_capital']/1000000*100:.1f}% of capital)")
                        logger.info(f"🎯 [TARGETS] T1: ₹{position['target1']:.2f}, T2: ₹{position['target2']:.2f}, T3: ₹{position['target3']:.2f}")
                
                # Status every 10 cycles
                if self.cycle_count % 10 == 0:
                    stats = self.engine.get_stats()
                    total_deployed = stats['total_deployed']
                    usage = stats['usage_percent']
                    open_pos = stats['open_positions']
                    
                    logger.info(f"📊 [STATUS] Cycle {self.cycle_count}: {open_pos} open, Deployed: ₹{total_deployed:,.2f} ({usage:.1f}%)")
                    
                    # Show position details
                    for pos in stats['positions']:
                        if pos.get('status') == 'OPEN':
                            symbol = pos.get('symbol')
                            entry = pos.get('entry_price', 0)
                            current = pos.get('current_price', entry)
                            pnl_pct = pos.get('pnl_percent', 0)
                            status = pos.get('status', 'OPEN')
                            logger.info(f"   📈 {symbol}: Entry ₹{entry:.2f} → Current ₹{current:.2f} ({pnl_pct:+.1f}%) [{status}]")
                        elif pos.get('status') in ['TARGET1', 'TARGET2', 'TARGET3']:
                            symbol = pos.get('symbol')
                            status = pos.get('status')
                            pnl = pos.get('pnl', 0)
                            target_hits[status] = target_hits.get(status, 0) + 1
                            if target_hits[status] <= 3:  # Only log first 3 hits
                                logger.info(f"🎯 [TARGET HIT] {symbol} {status}: +{pos.get('pnl_percent', 0):.1f}% (₹{pnl:,.2f})")
                
                # Update positions with current prices
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol in market_data:
                        self.engine.update_positions({'symbol': symbol, 'ltp': market_data[symbol].get('ltp', 0)})
                
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("[STOP] Interrupted by user")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                await asyncio.sleep(5)

async def main():
    system = AdvancedTradingSystem()
    await system.start_trading()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted by user")
