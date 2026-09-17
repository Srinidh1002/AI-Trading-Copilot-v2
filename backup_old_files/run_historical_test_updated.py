# run_historical_test_updated.py
# FIXED - Added missing _safe_int method

import asyncio
import logging
import sys
import os
import json
from pathlib import Path
from datetime import datetime
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine
from services.trading.adaptive_learning_engine import AdaptiveLearningEngine
from services.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class HistoricalDataPlayer:
    def __init__(self, data_file: str = "data/task9/live_stream/ticks-2026-09-02.jsonl"):
        self.data_file = Path(data_file)
        self.bridge = None
        self.engine = None
        self.is_running = False
        self.data_points = []
        self.processed_count = 0
        self.start_time = None
        self.ai_learning = AdaptiveLearningEngine()
        self.trade_count = 0
        
    def load_data(self) -> bool:
        if not self.data_file.exists():
            jsonl_files = list(Path("data/task9/live_stream").glob("ticks-*.jsonl"))
            if jsonl_files:
                self.data_file = sorted(jsonl_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                logger.info(f"[FILE] Found data file: {self.data_file.name}")
            else:
                logger.error("[ERROR] No data files found!")
                return False
        
        try:
            with open(self.data_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if data.get('market') in ['NIFTY', 'SENSEX']:
                            self.data_points.append(data)
                    except:
                        continue
            
            logger.info(f"[OK] Loaded {len(self.data_points)} data points")
            return len(self.data_points) > 0
            
        except Exception as e:
            logger.error(f"[ERROR] Error loading data: {e}")
            return False
    
    def _safe_float(self, value, default=0.0):
        """Safely convert to float"""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0):
        """Safely convert to int"""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    async def play(self, speed_multiplier: float = 0.05):
        if not self.data_points:
            logger.error("[ERROR] No data loaded")
            return
        
        logger.info(f"[PLAY] Playing {len(self.data_points)} data points with AI learning...")
        logger.info(f"[SPEED] Speed: {speed_multiplier}x")
        logger.info("[BRAIN] AI Self-Learning is ACTIVE!")
        logger.info("[LOT] NIFTY: 65 units/lot | SENSEX: 20 units/lot (SEBI 2026)")
        
        self.start_time = datetime.now()
        self.processed_count = 0
        
        chunk_size = 10
        
        for i in range(0, len(self.data_points), chunk_size):
            if not self.is_running:
                break
                
            chunk = self.data_points[i:i+chunk_size]
            
            for data in chunk:
                symbol = data.get('market')
                if not symbol:
                    continue
                
                ltp = self._safe_float(data.get('ltp', 0))
                volume = self._safe_int(data.get('volume', 0))
                high = self._safe_float(data.get('high_price', 0))
                low = self._safe_float(data.get('low_price', 0))
                open_price = self._safe_float(data.get('open_price', 0))
                close = self._safe_float(data.get('close_price', 0))
                
                tick_data = {
                    'symbol': symbol,
                    'ltp': ltp,
                    'timestamp': data.get('provider_timestamp', datetime.now().isoformat()),
                    'source': 'historical',
                    'volume': volume,
                    'high': high,
                    'low': low,
                    'open': open_price,
                    'close': close
                }
                
                if self.bridge:
                    self.bridge.latest_data[symbol] = tick_data
                    for subscriber in self.bridge.subscribers:
                        try:
                            if asyncio.iscoroutinefunction(subscriber):
                                await subscriber(tick_data)
                            else:
                                subscriber(tick_data)
                        except Exception as e:
                            logger.error(f"[ERROR] {e}")
                
                self.processed_count += 1
            
            if self.processed_count % 1000 == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                
                metrics = self.ai_learning.learning_engine.get_performance_metrics()
                trades = metrics.get('total_trades', 0)
                
                if trades > self.trade_count:
                    self.trade_count = trades
                    logger.info(f"[STATS] Processed {self.processed_count}/{len(self.data_points)} | Time: {minutes}m{seconds}s | AI Trades: {trades}")
                else:
                    logger.info(f"[STATS] Processed {self.processed_count}/{len(self.data_points)} | Time: {minutes}m{seconds}s")
            
            await asyncio.sleep(chunk_size * speed_multiplier)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        logger.info(f"[OK] Playback complete! Processed {self.processed_count} points in {minutes}m{seconds}s")
        
        # Show final AI report
        report = self.ai_learning.get_learning_report()
        logger.info(report)

async def main():
    logger.info("=" * 70)
    logger.info("[BRAIN] AI SELF-LEARNING TEST - UPDATED")
    logger.info("[LOT] NIFTY: 65 units/lot | SENSEX: 20 units/lot (SEBI 2026)")
    logger.info("=" * 70)
    logger.info("")
    
    bridge = WebSocketBridge('data/task9/live_stream')
    bridge.initialize()
    
    engine = AdvancedPaperTradingEngine(bridge)
    
    player = HistoricalDataPlayer()
    player.bridge = bridge
    player.is_running = True
    
    if not player.load_data():
        logger.error("[ERROR] Failed to load data")
        return
    
    logger.info("")
    logger.info("[STATS] Starting AI-powered trading engine...")
    
    engine_task = asyncio.create_task(engine.start())
    
    await asyncio.sleep(3)
    
    await player.play(speed_multiplier=0.05)
    
    logger.info("[WAIT] Waiting for final processing...")
    await asyncio.sleep(10)
    
    player.is_running = False
    engine.stop()
    
    logger.info("=" * 70)
    logger.info("[OK] AI LEARNING TEST COMPLETE")
    logger.info("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
