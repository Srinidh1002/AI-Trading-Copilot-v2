# run_historical_test_ai_fixed.py
# COMPLETE AI LEARNING TEST WITH FULL INTEGRATION

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

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

class HistoricalDataPlayer:
    """Plays historical data with AI learning"""
    
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
        """Load historical data"""
        if not self.data_file.exists():
            jsonl_files = list(Path("data/task9/live_stream").glob("ticks-*.jsonl"))
            if jsonl_files:
                self.data_file = sorted(jsonl_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                logger.info(f"📄 Found data file: {self.data_file.name}")
            else:
                logger.error("❌ No data files found!")
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
            
            logger.info(f"✅ Loaded {len(self.data_points)} data points")
            return len(self.data_points) > 0
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False
    
    def _safe_float(self, value, default=0.0):
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _safe_int(self, value, default=0):
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    async def play(self, speed_multiplier: float = 0.05):
        """Play data with AI learning"""
        if not self.data_points:
            logger.error("No data loaded")
            return
        
        logger.info(f"🔄 Playing {len(self.data_points)} data points with AI learning...")
        logger.info(f"⚡ Speed: {speed_multiplier}x")
        logger.info("🧠 AI Self-Learning is ACTIVE!")
        
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
                            logger.error(f"Error: {e}")
                
                self.processed_count += 1
            
            if self.processed_count % 1000 == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                
                # Check if AI has learned anything
                metrics = self.ai_learning.learning_engine.get_performance_metrics()
                trades = metrics.get('total_trades', 0)
                
                if trades > self.trade_count:
                    self.trade_count = trades
                    logger.info(f"📊 Processed {self.processed_count}/{len(self.data_points)} | Time: {minutes}m{seconds}s | AI Trades: {trades}")
                else:
                    logger.info(f"📊 Processed {self.processed_count}/{len(self.data_points)} | Time: {minutes}m{seconds}s")
            
            # Show AI learning progress every 10000 points
            if self.processed_count % 10000 == 0 and self.processed_count > 0:
                self._show_learning_progress()
            
            await asyncio.sleep(chunk_size * speed_multiplier)
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        logger.info(f"✅ Playback complete! Processed {self.processed_count} points in {minutes}m{seconds}s")
        
        # Show final AI learning report
        self._show_final_report()
    
    def _show_learning_progress(self):
        """Show AI learning progress"""
        metrics = self.ai_learning.learning_engine.get_performance_metrics()
        logger.info(f"""
🧠 AI LEARNING PROGRESS
  Trades: {metrics['total_trades']}
  Win Rate: {metrics['win_rate']:.1f}%
  Total P&L: ₹{metrics['total_pnl']:.2f}
  Learning Cycles: {metrics['learning_cycles']}
  Strategy Weights:
    Trend: {metrics['strategy_weights'].get('trend_following', 0):.2f}
    Breakout: {metrics['strategy_weights'].get('breakout', 0):.2f}
    RSI: {metrics['strategy_weights'].get('rsi_reversal', 0):.2f}
    Bias: {metrics['strategy_weights'].get('market_bias', 0):.2f}
""")
    
    def _show_final_report(self):
        """Show final AI learning report"""
        report = self.ai_learning.get_learning_report()
        logger.info(report)

async def main():
    logger.info("=" * 70)
    logger.info("🧠 AI SELF-LEARNING TEST - FIXED VERSION")
    logger.info("=" * 70)
    logger.info("")
    
    bridge = WebSocketBridge('data/task9/live_stream')
    bridge.initialize()
    
    engine = AdvancedPaperTradingEngine(bridge)
    
    player = HistoricalDataPlayer()
    player.bridge = bridge
    player.is_running = True
    
    if not player.load_data():
        logger.error("❌ Failed to load data")
        return
    
    logger.info("")
    logger.info("📊 Starting AI-powered trading engine...")
    
    engine_task = asyncio.create_task(engine.start())
    
    await asyncio.sleep(3)
    
    await player.play(speed_multiplier=0.05)
    
    logger.info("⏳ Waiting for final processing...")
    await asyncio.sleep(10)
    
    player.is_running = False
    engine.stop()
    
    logger.info("=" * 70)
    logger.info("✅ AI LEARNING TEST COMPLETE")
    logger.info("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
