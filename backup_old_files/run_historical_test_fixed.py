# run_historical_test_fixed.py
# Fixed version that properly connects the engine to tick data

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine
from services.utils.logging_utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# LOT SIZES (SEBI 2026)
LOT_SIZES = {
    'NIFTY': 65,
    'SENSEX': 20
}

class HistoricalDataPlayer:
    """Play historical data with engine connection."""
    
    def __init__(self, data_file: str = None, engine: AdvancedPaperTradingEngine = None):
        self.data_file = data_file
        self.engine = engine
        self.data = []
        self.is_running = False
        self.trade_count = 0
        self.last_trade_time = None
        
    def load_data(self):
        """Load historical data from file."""
        if self.data_file is None:
            # Try to find data file
            data_dir = Path("data/task9/live_stream")
            files = sorted(data_dir.glob("ticks-*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
            if files:
                self.data_file = files[0]
                logger.info(f"[LOAD] Found data file: {self.data_file}")
            else:
                logger.error("[ERROR] No data file found")
                return False
        
        try:
            with open(self.data_file, 'r') as f:
                content = f.read()
                # Handle JSONL format (each line is a JSON object)
                if content.strip():
                    lines = content.strip().split('\n')
                    for line in lines:
                        try:
                            tick = json.loads(line)
                            self.data.append(tick)
                        except json.JSONDecodeError:
                            continue
                    
                    logger.info(f"[LOAD] Loaded {len(self.data)} ticks from {self.data_file}")
                    return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to load data: {e}")
            return False
    
    async def play(self, speed_multiplier: float = 0.05):
        """Play through the data, sending ticks to the engine."""
        if not self.data:
            logger.error("[ERROR] No data to play")
            return
        
        self.is_running = True
        logger.info(f"[PLAY] Playing {len(self.data)} data points with AI learning...")
        logger.info(f"[SPEED] Speed: {speed_multiplier}x")
        
        # Track NIFTY and SENSEX separately
        symbols_data = {}
        last_process_time = datetime.now()
        
        for i, tick in enumerate(self.data):
            if not self.is_running:
                break
            
            symbol = tick.get('symbol', '')
            ltp = tick.get('ltp', 0)
            timestamp = tick.get('timestamp', datetime.now().isoformat())
            
            if not symbol or ltp <= 0:
                continue
            
            # Store latest data for each symbol
            symbols_data[symbol] = {
                'ltp': ltp,
                'timestamp': timestamp,
                'symbol': symbol
            }
            
            # Process tick through engine
            if self.engine:
                try:
                    # Call the engine's analyze_signal method
                    signal = await self.engine.analyze_signal({
                        'symbol': symbol,
                        'ltp': ltp,
                        'timestamp': timestamp
                    })
                    
                    if signal and signal.get('signal') == 'TRADE':
                        # Enter the position
                        position = self.engine._enter_option_position(
                            {'symbol': symbol, 'ltp': ltp},
                            'CALL',
                            signal,
                            {}
                        )
                        if position:
                            self.trade_count += 1
                            self.last_trade_time = datetime.now()
                            logger.info(f"[TRADE #{self.trade_count}] {symbol} @ ₹{position['entry_price']:.2f} premium")
                            
                            # Update positions after trade
                            self.engine.update_positions({'symbol': symbol, 'ltp': ltp})
                            
                            # Print summary every few trades
                            if self.trade_count % 1 == 0:
                                stats = self.engine.get_stats()
                                logger.info(f"[STATS] Trades: {self.trade_count}, Deployed: ₹{stats['total_deployed']:,.2f} ({stats['usage_percent']:.1f}%)")
                    
                    # Update positions even if no trade
                    self.engine.update_positions({'symbol': symbol, 'ltp': ltp})
                    
                except Exception as e:
                    logger.error(f"[ERROR] Processing tick: {e}")
            
            # Progress reporting
            if (i + 1) % 1000 == 0:
                elapsed = (datetime.now() - last_process_time).total_seconds()
                logger.info(f"[STATS] Processed {i+1}/{len(self.data)} | Time: {elapsed:.0f}s")
                last_process_time = datetime.now()
                
                # Show current positions
                if self.engine and self.engine.positions:
                    stats = self.engine.get_stats()
                    logger.info(f"[POSITIONS] {stats['open_positions']} open, Deployed: ₹{stats['total_deployed']:,.2f}")
            
            # Simulate real-time speed
            await asyncio.sleep(0.01 * speed_multiplier)
        
        self.is_running = False
        logger.info("[PLAY] Playback complete")
    
    def stop(self):
        """Stop playback."""
        self.is_running = False


async def main():
    """Main entry point."""
    print("=" * 70)
    print("🧠 AI SELF-LEARNING TEST - FIXED")
    print("=" * 70)
    
    # Get capital from user or use default
    capital = 1000000  # ₹10,00,000
    print(f"[LOT] NIFTY: 65 units/lot | SENSEX: 20 units/lot (SEBI 2026)")
    print(f"[CAPITAL] ₹{capital:,.2f}")
    print("=" * 70)
    print("")
    
    # Create engine
    engine = AdvancedPaperTradingEngine(capital=capital, max_positions=2)
    await engine.start()
    logger.info("[START] Advanced Paper Trading Engine started")
    
    # Create data player
    player = HistoricalDataPlayer(engine=engine)
    if not player.load_data():
        logger.error("[ERROR] Failed to load data. Exiting.")
        await engine.stop()
        return
    
    # Play data
    try:
        await player.play(speed_multiplier=0.05)
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted by user")
    
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
        print("\nPOSITIONS:")
        for pos in engine.positions:
            status = pos.get('status', 'UNKNOWN')
            print(f"  {pos['symbol']} {pos['option_type']} @ ₹{pos['entry_price']:.2f} [{status}]")
            print(f"    Lots: {pos['lots']}, Qty: {pos['quantity']}")
            print(f"    Deployed: ₹{pos['deployed_capital']:,.2f}")
            print(f"    P&L: ₹{pos.get('pnl', 0):,.2f} ({pos.get('pnl_percent', 0):.1f}%)")
            print(f"    Underlying: ₹{pos['underlying_price']:.2f}")
    
    print("=" * 70)
    
    await engine.stop()
    logger.info("[STOP] Advanced Paper Trading Engine stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[STOP] Interrupted by user")
