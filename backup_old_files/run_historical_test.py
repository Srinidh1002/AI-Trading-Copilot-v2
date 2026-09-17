# run_historical_test.py
# Run this to test with historical data

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

class HistoricalTestRunner:
    """Runs system with historical data"""
    
    def __init__(self, target_trades=100):
        self.target_trades = target_trades
        self.engine = None
        self.is_running = False
        
    async def run(self):
        try:
            logger.info("=" * 70)
            logger.info("📜 HISTORICAL DATA TEST MODE")
            logger.info("=" * 70)
            logger.info("🔄 Playing back historical data...")
            
            # Initialize WebSocket Bridge
            bridge = WebSocketBridge('data/task9/live_stream')
            bridge.initialize()
            
            # Initialize Engine
            self.engine = AdvancedPaperTradingEngine(bridge)
            self.is_running = True
            
            # Start engine
            engine_task = asyncio.create_task(self.engine.start())
            
            # Monitor progress
            await self._monitor_progress()
            
            if not engine_task.done():
                engine_task.cancel()
                try:
                    await engine_task
                except asyncio.CancelledError:
                    pass
            
        except KeyboardInterrupt:
            logger.info("🛑 Test stopped by user")
            if self.engine:
                self.engine.stop()
        except Exception as e:
            logger.error(f"❌ Error: {e}")
    
    async def _monitor_progress(self):
        """Monitor progress"""
        last_check = 0
        no_progress_count = 0
        
        while self.is_running:
            await asyncio.sleep(10)
            
            if not self.engine:
                continue
            
            trades = self.engine.trades
            total_trades = len(trades)
            winning = sum(1 for t in trades if t.get('pnl_percent', 0) > 0)
            
            if total_trades != last_check:
                logger.info("=" * 70)
                logger.info(f"📊 PROGRESS: {total_trades} trades, Win Rate: {(winning/total_trades*100) if total_trades > 0 else 0:.1f}%")
                logger.info("=" * 70)
                
                if total_trades >= self.target_trades:
                    logger.info(f"🎉 TARGET ACHIEVED: {self.target_trades} trades completed!")
                    self.is_running = False
                    if self.engine:
                        self.engine.stop()
                    return
                
                last_check = total_trades
                no_progress_count = 0
            else:
                no_progress_count += 1
                if no_progress_count > 30:  # 5 minutes no progress
                    logger.info("⏰ No progress for 5 minutes. Stopping test.")
                    self.is_running = False
                    if self.engine:
                        self.engine.stop()
                    return

async def main():
    runner = HistoricalTestRunner(target_trades=100)
    await runner.run()

if __name__ == "__main__":
    asyncio.run(main())
