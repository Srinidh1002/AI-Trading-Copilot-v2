# services/market/websocket_bridge.py - FIXED: Looks in multiple locations

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSocketBridge:
    """WebSocket bridge for market data."""
    
    def __init__(self, data_dir: str = "data/task9/live_stream"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.subscribers = []
        self.latest_data = {}
        self.is_running = False
        self.symbols = ['NIFTY', 'SENSEX']
        self.all_data = []  # Store all ticks for playback
        
    def initialize(self):
        """Initialize the bridge."""
        logger.info(f"WebSocket Bridge monitoring: {self.data_dir}")
        self.is_running = True
        
        # Check multiple locations for data
        locations = [
            self.data_dir,
            Path("data/paper_trading/certified_runtime/task9/live_stream"),
        ]
        
        all_files = []
        for loc in locations:
            if loc.exists():
                files = sorted(loc.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
                for f in files:
                    all_files.append(f)
        
        # Load data from all files
        for file_path in all_files[:3]:  # Limit to 3 files
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if content.strip():
                        # Try to parse as JSON
                        try:
                            data = json.loads(content)
                            if isinstance(data, dict) and "ticks" in data:
                                # Format with ticks array
                                for tick in data.get("ticks", []):
                                    self._process_tick(tick)
                            elif isinstance(data, list):
                                # Array of ticks
                                for tick in data:
                                    self._process_tick(tick)
                            else:
                                # JSONL format
                                lines = content.strip().split('\n')
                                for line in lines:
                                    try:
                                        tick = json.loads(line)
                                        self._process_tick(tick)
                                    except:
                                        pass
                        except json.JSONDecodeError:
                            # JSONL format
                            lines = content.strip().split('\n')
                            for line in lines:
                                try:
                                    tick = json.loads(line)
                                    self._process_tick(tick)
                                except:
                                    pass
            except Exception as e:
                logger.warning(f"[BRIDGE] Could not load {file_path}: {e}")
        
        if self.latest_data:
            logger.info(f"[BRIDGE] Loaded data for: {list(self.latest_data.keys())}")
            for symbol, data in self.latest_data.items():
                logger.info(f"[BRIDGE] {symbol}: LTP={data.get('ltp', 0)}")
        else:
            logger.warning("[BRIDGE] No data loaded. Using synthetic data for testing.")
            # Generate synthetic data
            base_prices = {'NIFTY': 23864.55, 'SENSEX': 76413.50}
            for symbol in self.symbols:
                self.latest_data[symbol] = {
                    'ltp': base_prices[symbol],
                    'timestamp': datetime.now().isoformat()
                }
            logger.info("[BRIDGE] Generated synthetic data")
        
        # Start polling
        asyncio.create_task(self._poll_data())
        return self
    
    def _process_tick(self, tick):
        """Process a single tick."""
        try:
            symbol = tick.get('market', tick.get('symbol', ''))
            if symbol in self.symbols:
                ltp = tick.get('ltp', 0)
                if ltp > 0:
                    # Store in all_data for playback
                    self.all_data.append(tick)
                    # Keep latest data
                    self.latest_data[symbol] = {
                        'ltp': ltp,
                        'timestamp': tick.get('provider_timestamp', tick.get('timestamp', datetime.now().isoformat()))
                    }
        except:
            pass
    
    async def _poll_data(self):
        """Poll for new data (for real-time)."""
        while self.is_running:
            try:
                # Check for new files in data_dir
                files = sorted(self.data_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
                if files:
                    latest = files[0]
                    # Check if new data
                    with open(latest, 'r') as f:
                        content = f.read()
                        if content.strip():
                            lines = content.strip().split('\n')
                            for line in lines:
                                try:
                                    tick = json.loads(line)
                                    self._process_tick(tick)
                                except:
                                    pass
            except Exception as e:
                logger.debug(f"[BRIDGE] Poll error: {e}")
            
            await asyncio.sleep(2)
    
    def get_latest_data(self):
        """Get the latest market data."""
        return self.latest_data
    
    def get_all_data(self):
        """Get all stored data."""
        return self.all_data
    
    def subscribe(self, callback):
        """Subscribe to data updates."""
        self.subscribers.append(callback)
        return len(self.subscribers) - 1
    
    def unsubscribe(self, index):
        """Unsubscribe from data updates."""
        if index < len(self.subscribers):
            self.subscribers.pop(index)
    
    def stop(self):
        """Stop the bridge."""
        self.is_running = False
