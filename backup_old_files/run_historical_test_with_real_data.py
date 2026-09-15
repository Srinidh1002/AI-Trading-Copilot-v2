# run_historical_test_with_real_data.py
# FIXED: Handles the correct tick file format

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealDataPlayer:
    """Play real tick data from live_stream directory."""
    
    def __init__(self, engine: AdvancedPaperTradingEngine = None):
        self.engine = engine
        self.data = []
        self.is_running = False
        self.trade_count = 0
        
    def load_data(self):
        """Load tick data from live_stream directory."""
        data_dir = Path("data/paper_trading/certified_runtime/task9/live_stream")
        if not data_dir.exists():
            data_dir = Path("data/task9/live_stream")
        
        if not data_dir.exists():
            logger.error(f"[ERROR] Data directory not found: {data_dir}")
            return False
        
        files = sorted(data_dir.glob("ticks-*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not files:
            logger.error(f"[ERROR] No tick files found in {data_dir}")
            return False
        
        latest_file = files[0]
        logger.info(f"[LOAD] Loading data from: {latest_file}")
        
        try:
            with open(latest_file, 'r') as f:
                data = json.load(f)
                # Check if data is a dict with "ticks" key
                if isinstance(data, dict) and "ticks" in data:
                    raw_ticks = data.get("ticks", [])
                    logger.info(f"[LOAD] Found {len(raw_ticks)} ticks in 'ticks' array")
                elif isinstance(data, list):
                    raw_ticks = data
                    logger.info(f"[LOAD] Found {len(raw_ticks)} ticks in JSON array")
                else:
                    logger.error(f"[ERROR] Unknown data format: {type(data)}")
                    return False
                
                # Extract only NIFTY and SENSEX
                for tick in raw_ticks:
                    market = tick.get('market', '')
                    if market in ['NIFTY', 'SENSEX']:
                        self.data.append({
                            'symbol': market,
                            'ltp': tick.get('ltp', 0),
                            'timestamp': tick.get('provider_timestamp', tick.get('received_at', datetime.now().isoformat()))
                        })
                
                logger.info(f"[LOAD] Loaded {len(self.data)} ticks (NIFTY/SENSEX)")
                return True
                
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] JSON decode error: {e}")
            return False
        except Exception as e:
            logger.error(f"[ERROR] Failed to load data: {e}")
            return False
    
    async def play(self, speed_multiplier: float = 0.005, max_ticks: int = 2000):
        """Play through the data."""
        if not self.data:
            logger.error("[ERROR] No data to play")
            return
        
        self.is_running = True
        total_ticks = min(len(self.data), max_ticks)
        logger.info(f"[PLAY] Playing {total_ticks} ticks...")
        
        processed = 0
        last_progress = datetime.now()
        
        for i, tick in enumerate(self.data[:total_ticks]):
            if not self.is_running:
                break
            
            symbol = tick.get('symbol', '')
            ltp = tick.get('ltp', 0)
            
            if not symbol or ltp <= 0:
                continue
            
            # Process through engine
            if self.engine:
                try:
                    # Analyze signal
                    signal = await self.engine.analyze_signal({
                        'symbol': symbol,
                        'ltp': ltp,
                        'timestamp': tick.get('timestamp', datetime.now().isoformat())
                    })
                    
                    if signal and signal.get('signal') == 'TRADE':
                        # Enter position
                        position = self.engine._enter_option_position(
                            {'symbol': symbol, 'ltp': ltp},
                            'CALL',
                            signal,
                            {}
                        )
                        if position:
                            self.trade_count += 1
                            logger.info(f"[TRADE #{self.trade_count}] {symbol} @ ₹{position['entry_price']:.2f} premium")
                            
                            stats = self.engine.get_stats()
                            logger.info(f"[STATS] Deployed: ₹{stats['total_deployed']:,.2f} ({stats['usage_percent']:.1f}%)")
                    
                    # Update positions
                    self.engine.update_positions({'symbol': symbol, 'ltp': ltp})
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"[ERROR] Processing tick: {e}")
            
            # Progress every 200 ticks
            if (i + 1) % 200 == 0:
                elapsed = (datetime.now() - last_progress).total_seconds()
                logger.info(f"[PROGRESS] {i+1}/{total_ticks} ticks | {elapsed:.1f}s")
                last_progress = datetime.now()
                
                if self.engine and self.engine.positions:
                    stats = self.engine.get_stats()
                    logger.info(f"[POSITIONS] {stats['open_positions']} open, Deployed: ₹{stats['total_deployed']:,.2f}")
            
            # Control speed
            await asyncio.sleep(0.005 / speed_multiplier if speed_multiplier > 0 else 0.01)
        
        self.is_running = False
        logger.info(f"[PLAY] Playback complete. Processed {processed} ticks.")


async def main():
    """Main entry point."""
    print("=" * 70)
    print("📊 REAL DATA HISTORICAL TEST")
    print("=" * 70)
    
    capital = 1000000
    print(f"[CAPITAL] ₹{capital:,.2f}")
    print(f"[LOT] NIFTY: 65 | SENSEX: 20 (SEBI 2026)")
    print("=" * 70)
    
    # Create engine
    engine = AdvancedPaperTradingEngine(capital=capital, max_positions=2)
    await engine.start()
    
    # Create player
    player = RealDataPlayer(engine=engine)
    if not player.load_data():
        print("[ERROR] Failed to load data")
        await engine.stop()
        return
    
    # Play data
    try:
        await player.play(speed_multiplier=0.005, max_ticks=2000)
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
    
    # Show final stats
    stats = engine.get_stats()
    print("\n" + "=" * 70)
    print("📊 FINAL STATISTICS")
    print("=" * 70)
    print(f"Total Positions: {stats['total_positions']}")
    print(f"Open Positions: {stats['open_positions']}")
    print(f"Total Deployed: ₹{stats['total_deployed']:,.2f}")
    print(f"Usage: {stats['usage_percent']:.1f}%")
    print(f"Available Capital: ₹{stats['available_capital']:,.2f}")
    
    if engine.positions:
        print("\n📈 POSITIONS:")
        for pos in engine.positions:
            status = pos.get('status', 'UNKNOWN')
            pnl = pos.get('pnl', 0)
            pnl_pct = pos.get('pnl_percent', 0)
            print(f"  {pos['symbol']} {pos['option_type']} @ ₹{pos['entry_price']:.2f} [{status}]")
            print(f"    P&L: ₹{pnl:,.2f} ({pnl_pct:.1f}%) | Deployed: ₹{pos['deployed_capital']:,.2f}")
    
    print("=" * 70)
    
    await engine.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user")
