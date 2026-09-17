# test_trading_with_historical_data.py
# Run this to test the trading logic with existing data

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.market.websocket_bridge import WebSocketBridge
from services.trading.paper_engine import PaperTradingEngine

# Simple ASCII logging
class AsciiFilter(logging.Filter):
    def filter(self, record):
        record.msg = record.msg.replace('\U0001f680', '[START]')
        record.msg = record.msg.replace('\u2705', '[OK]')
        record.msg = record.msg.replace('\U0001f4dd', '[NOTE]')
        record.msg = record.msg.replace('\U0001f4ca', '[STATS]')
        record.msg = record.msg.replace('\U0001f50c', '[CONNECT]')
        record.msg = record.msg.replace('\U0001f4c2', '[FOLDER]')
        record.msg = record.msg.replace('\u2705', '[OK]')
        return True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Add filter to root logger
for handler in logging.root.handlers:
    handler.addFilter(AsciiFilter())

logger = logging.getLogger(__name__)

class HistoricalDataPlayer:
    """Play historical data as if it's real-time"""
    
    def __init__(self, bridge, speed_multiplier=1.0):
        self.bridge = bridge
        self.speed_multiplier = speed_multiplier
        self.data_points = []
        self.current_index = 0
        self.is_running = False
        
    def load_data(self, jsonl_file):
        """Load data from JSONL file"""
        logger.info(f"[NOTE] Loading data from: {jsonl_file}")
        with open(jsonl_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get('market') in ['NIFTY', 'SENSEX']:
                        self.data_points.append(data)
                except:
                    continue
        logger.info(f"[OK] Loaded {len(self.data_points)} data points")
        
    async def play(self):
        """Play data as if real-time"""
        self.is_running = True
        logger.info("[START] Playing historical data...")
        
        while self.is_running and self.current_index < len(self.data_points):
            # Get a batch of data points
            batch = []
            while self.current_index < len(self.data_points):
                batch.append(self.data_points[self.current_index])
                self.current_index += 1
                # Process 10 points at a time
                if len(batch) >= 10:
                    break
            
            # Process each point
            for data in batch:
                # Convert to tick format
                tick_data = {
                    'symbol': data.get('market'),
                    'ltp': float(data.get('ltp', 0)),
                    'timestamp': data.get('provider_timestamp'),
                    'source': 'historical'
                }
                
                # Update bridge
                symbol = tick_data['symbol']
                self.bridge.latest_data[symbol] = tick_data
                
                # Notify subscribers
                for subscriber in self.bridge.subscribers:
                    try:
                        if asyncio.iscoroutinefunction(subscriber):
                            await subscriber(tick_data)
                        else:
                            subscriber(tick_data)
                    except Exception as e:
                        logger.error(f"Error: {e}")
            
            # Wait to simulate real-time
            await asyncio.sleep(0.1 * self.speed_multiplier)
            
            # Print progress
            if self.current_index % 1000 == 0:
                logger.info(f"[STATS] Processed {self.current_index}/{len(self.data_points)} points")
                
        logger.info(f"[OK] Finished playing data. Processed {self.current_index} points")

async def main():
    try:
        logger.info("=" * 60)
        logger.info("[START] AI Trading Copilot - Historical Test Mode")
        logger.info("=" * 60)
        
        # Initialize bridge
        bridge = WebSocketBridge('data/task9/live_stream')
        bridge.initialize()
        
        # Initialize trading engine
        engine = PaperTradingEngine(bridge)
        
        # Load historical data
        jsonl_files = list(Path('data/task9/live_stream').glob('ticks-*.jsonl'))
        if jsonl_files:
            latest = sorted(jsonl_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            
            player = HistoricalDataPlayer(bridge, speed_multiplier=0.01)
            player.load_data(latest)
            
            # Start engine
            logger.info("[START] Starting paper trading engine...")
            asyncio.create_task(engine.start())
            
            # Wait for engine to initialize
            await asyncio.sleep(2)
            
            # Play historical data
            await player.play()
            
        else:
            logger.error("[ERROR] No JSONL files found")
            
    except KeyboardInterrupt:
        logger.info("[STOP] Shutting down...")
        if 'engine' in locals():
            engine.stop()
        if 'player' in locals():
            player.is_running = False
    except Exception as e:
        logger.error(f"[ERROR] Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
