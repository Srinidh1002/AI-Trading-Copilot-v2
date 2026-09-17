import threading
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class LiveOptionChainCache:
    """
    Background cache that polls the Angel One FULL options endpoint at a fixed interval.
    This entirely decouples the parent cycle from network rate limits.
    """
    def __init__(self, market_client, clock, refresh_interval_seconds=60.0):
        self.market_client = market_client
        self.clock = clock
        self.refresh_interval = refresh_interval_seconds
        
        self._cache = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self, option_exchange, tokens):
        """Starts the background polling thread."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop, 
            args=(option_exchange, tokens),
            daemon=True,
            name="OptionChainPoller"
        )
        self._thread.start()
        logger.info(f"Started background Option Chain cache (Interval: {self.refresh_interval}s)")

    def stop(self):
        """Stops the background thread gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _poll_loop(self, option_exchange, tokens):
        while self._running:
            try:
                # 1. Fetch the data
                response = self.market_client.get_market_data(
                    mode="FULL",
                    exchange_tokens={option_exchange: tokens}
                )
                
                # 2. Store it safely with a timestamp
                with self._lock:
                    self._cache = {
                        "response": response,
                        "received_at": self.clock()
                    }
                    
            except Exception as e:
                logger.error(f"Background Option Chain cache update failed: {e}")
            
            # Wait for the next cycle
            time.sleep(self.refresh_interval)

    def get_latest_chain(self):
        """Returns the latest chain response and receipt timestamp."""
        with self._lock:
            if not self._cache:
                return None, None
            return self._cache["response"], self._cache["received_at"]