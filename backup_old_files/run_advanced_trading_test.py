# run_advanced_trading_test.py - FIXED LOGGING

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, time
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine
from services.utils.logging_utils import setup_logging

# Setup logging with emoji filter
setup_logging()
logger = logging.getLogger(__name__)

class TestRunner:
    """Runs system until 100 successful trades are completed"""
    
    def __init__(self, target_trades=100, target_per_index=50):
        self.target_trades = target_trades
        self.target_per_index = target_per_index
        self.engine = None
        self.is_running = False
        self.start_time = None
        
    async def run(self):
        """Run until 100 trades are completed"""
        try:
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)
            
            # Check if market is open or we're in test mode
            market_open = time(9, 15)
            market_close = time(15, 30)
            current_time = now.time()
            
            if current_time < market_open or current_time > market_close:
                logger.info("=" * 70)
                logger.info("[WARN] Market is currently closed")
                logger.info(f"[DATE] Current IST: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                logger.info("[STATS] Running with historical data for testing...")
                logger.info("=" * 70)
            
            logger.info("=" * 70)
            logger.info(f"[TEST] TEST MODE: Target {self.target_trades} Successful Trades")
            logger.info(f"[STATS] Target per index: {self.target_per_index} each (NIFTY & SENSEX)")
            logger.info("=" * 70)
            
            # Initialize WebSocket Bridge
            bridge = WebSocketBridge('data/task9/live_stream')
            bridge.initialize()
            
            # Initialize Engine
            self.engine = AdvancedPaperTradingEngine(bridge)
            self.is_running = True
            self.start_time = datetime.now()
            
            # Start engine
            engine_task = asyncio.create_task(self.engine.start())
            
            # Monitor progress
            await self._monitor_progress()
            
            # Cancel engine task if still running
            if not engine_task.done():
                engine_task.cancel()
                try:
                    await engine_task
                except asyncio.CancelledError:
                    pass
            
        except KeyboardInterrupt:
            logger.info("[STOP] Test stopped by user")
            if self.engine:
                self.engine.stop()
        except Exception as e:
            logger.error(f"[ERROR] Error: {e}")
    
    async def _monitor_progress(self):
        """Monitor progress towards 100 trades"""
        last_check = 0
        no_data_count = 0
        
        while self.is_running:
            await asyncio.sleep(5)
            
            if not self.engine:
                continue
            
            trades = self.engine.trades
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.get('pnl_percent', 0) > 0)
            
            nifty_trades = sum(1 for t in trades if t.get('symbol') == 'NIFTY')
            sensex_trades = sum(1 for t in trades if t.get('symbol') == 'SENSEX')
            nifty_wins = sum(1 for t in trades if t.get('symbol') == 'NIFTY' and t.get('pnl_percent', 0) > 0)
            sensex_wins = sum(1 for t in trades if t.get('symbol') == 'SENSEX' and t.get('pnl_percent', 0) > 0)
            
            if total_trades == last_check:
                no_data_count += 1
                if no_data_count > 12:
                    logger.info("[WAIT] Waiting for trades... (no new trades for 1 minute)")
                    no_data_count = 0
            else:
                no_data_count = 0
            
            if total_trades != last_check:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                
                logger.info("=" * 70)
                logger.info(f"[STATS] PROGRESS: {total_trades}/{self.target_trades} trades")
                logger.info(f"[TIME] Elapsed: {minutes}m {seconds}s")
                logger.info(f"[STATS] Win Rate: {(winning_trades/total_trades*100) if total_trades > 0 else 0:.1f}%")
                logger.info("=" * 70)
                logger.info(f"[STATS] NIFTY: {nifty_trades} trades, {nifty_wins} wins")
                logger.info(f"[STATS] SENSEX: {sensex_trades} trades, {sensex_wins} wins")
                logger.info("=" * 70)
                
                if total_trades >= self.target_trades:
                    logger.info("[SUCCESS] TARGET ACHIEVED: 100 successful trades completed!")
                    logger.info("[OK] Test completed successfully!")
                    self.is_running = False
                    if self.engine:
                        self.engine.stop()
                    return
                
                if nifty_wins >= self.target_per_index and sensex_wins >= self.target_per_index:
                    logger.info("[SUCCESS] BOTH INDICES REACHED TARGET!")
                    logger.info(f"[OK] NIFTY: {nifty_wins}/50 wins")
                    logger.info(f"[OK] SENSEX: {sensex_wins}/50 wins")
                    self.is_running = False
                    if self.engine:
                        self.engine.stop()
                    return
                
                last_check = total_trades
            
            if total_trades > 0 and (datetime.now() - self.start_time).total_seconds() > 14400:
                logger.info("[TIME] 4 hours elapsed. Stopping test.")
                self.is_running = False
                if self.engine:
                    self.engine.stop()
                return

async def main():
    runner = TestRunner(target_trades=100, target_per_index=50)
    await runner.run()

if __name__ == "__main__":
    asyncio.run(main())
