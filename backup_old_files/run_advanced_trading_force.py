# run_advanced_trading_force.py
# FORCE START - Skips market hour checks for testing

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine
from services.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class AdvancedTradingSystem:
    """Complete trading system - FORCE START MODE"""
    
    def __init__(self):
        self.engine = None
        self.bridge = None
        self.is_running = False
        
    async def start(self):
        """Start the system immediately (no market hour checks)"""
        try:
            logger.info("=" * 80)
            logger.info("[START] ADVANCED TRADING - FORCE MODE")
            logger.info("=" * 80)
            
            # Initialize WebSocket Bridge
            self.bridge = WebSocketBridge('data/task9/live_stream')
            self.bridge.initialize()
            logger.info("[BRIDGE] WebSocket Bridge initialized")
            
            # Initialize Engine (with PREMIUM calculations)
            self.engine = AdvancedPaperTradingEngine(
                bridge=self.bridge,
                capital=1000000,
                max_positions=2
            )
            await self.engine.start()
            logger.info("[ENGINE] Trading Engine started (PREMIUM-based)")
            
            # Run the main loop
            await self.run_trading_loop()
            
        except KeyboardInterrupt:
            logger.info("[STOP] Interrupted by user")
        except Exception as e:
            logger.error(f"[ERROR] {e}")
        finally:
            if self.engine:
                await self.engine.stop()
    
    async def run_trading_loop(self):
        """Main trading loop"""
        self.is_running = True
        cycle = 0
        
        logger.info("=" * 60)
        logger.info("[TRADING] Starting automated paper trading...")
        logger.info("[NOTE] Using PREMIUM-based calculations")
        logger.info("=" * 60)
        
        while self.is_running:
            try:
                cycle += 1
                
                # Get live data
                market_data = {}
                if self.bridge and hasattr(self.bridge, 'get_latest_data'):
                    try:
                        market_data = self.bridge.get_latest_data()
                    except:
                        pass
                
                # Process NIFTY and SENSEX
                for symbol in ['NIFTY', 'SENSEX']:
                    if symbol in market_data:
                        tick = market_data[symbol]
                        ltp = tick.get('ltp', 0)
                        
                        if ltp <= 0:
                            continue
                        
                        # Get premium (calculated from underlying)
                        premium = self.engine.get_option_premium(symbol, ltp, 'CALL')
                        
                        # Check if we can enter a trade
                        open_positions = [p for p in self.engine.positions if p.get('status') == 'OPEN']
                        if len(open_positions) < self.engine.max_positions:
                            # Analyze signal
                            signal = await self.engine.analyze_signal({
                                'symbol': symbol,
                                'ltp': ltp,
                                'timestamp': datetime.now().isoformat()
                            })
                            
                            if signal and signal.get('signal') == 'TRADE':
                                # Enter position with PREMIUM
                                position = self.engine._enter_option_position(
                                    {'symbol': symbol, 'ltp': ltp},
                                    'CALL',
                                    signal,
                                    {}
                                )
                                if position:
                                    logger.info(f"[TRADE] {symbol} CALL @ ₹{position['entry_price']:.2f} premium")
                                    logger.info(f"[COST] Deployed: ₹{position['deployed_capital']:,.2f} ({position['deployed_capital']/1000000*100:.1f}% of capital)")
                        
                        # Update positions
                        self.engine.update_positions({'symbol': symbol, 'ltp': ltp})
                
                # Status every 10 cycles
                if cycle % 10 == 0:
                    stats = self.engine.get_stats()
                    logger.info(f"[STATUS] Cycle {cycle}: {stats['open_positions']} open, Deployed: ₹{stats['total_deployed']:,.2f} ({stats['usage_percent']:.1f}%)")
                
                # Wait before next cycle
                await asyncio.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("[STOP] Interrupted")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"[ERROR] {e}")
                await asyncio.sleep(5)

async def main():
    system = AdvancedTradingSystem()
    await system.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted by user")
