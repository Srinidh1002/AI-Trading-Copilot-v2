"""
Market Snapshot - Live market data from Angel One API
"""
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Angel One client singleton
_angel_client = None

def _get_angel_client():
    """Get or create Angel One client."""
    global _angel_client
    if _angel_client is None:
        try:
            from services.broker.angel_client import AngelMarketDataClient
            _angel_client = AngelMarketDataClient()
            logger.info("Angel One client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Angel One client: {e}")
            return None
    return _angel_client


def get_market_snapshot(market: str = "NIFTY") -> Dict:
    """
    Get live market snapshot from Angel One API.
    
    Args:
        market: "NIFTY" or "SENSEX"
        
    Returns:
        Dict with market data
    """
    # Try Angel One first
    client = _get_angel_client()
    
    if client is not None:
        try:
            # Map market to Angel One symbols
            symbol_map = {
                "NIFTY": ("NSE", "NIFTY", "99926000"),
                "SENSEX": ("BSE", "SENSEX", "99919000")
            }
            exchange, symbol, token = symbol_map.get(market, ("NSE", "NIFTY", "99926000"))
            
            # Use get_ltp method - we know this works from the test
            if hasattr(client, 'get_ltp'):
                try:
                    response = client.get_ltp(exchange, symbol, token)
                    logger.info(f"get_ltp response: {response}")
                    
                    # Parse the response - Angel One returns {'status': True, 'data': {'ltp': xxx, ...}}
                    if response and isinstance(response, dict):
                        # Check if response has 'data' field with 'ltp'
                        if 'data' in response and isinstance(response['data'], dict):
                            price = float(response['data'].get('ltp', 0))
                            volume = float(response['data'].get('volume', 0))
                            if price > 0:
                                logger.info(f"Got live data for {market}: {price}")
                                return {
                                    "market": market,
                                    "symbol": symbol,
                                    "price": price,
                                    "timestamp": datetime.now(),
                                    "volume": volume,
                                    "market_open": True,
                                    "data_source": "angel_one"
                                }
                        # Fallback: try direct ltp field
                        elif 'ltp' in response:
                            price = float(response.get('ltp', 0))
                            if price > 0:
                                logger.info(f"Got live data for {market}: {price}")
                                return {
                                    "market": market,
                                    "symbol": symbol,
                                    "price": price,
                                    "timestamp": datetime.now(),
                                    "volume": response.get('volume', 0),
                                    "market_open": True,
                                    "data_source": "angel_one"
                                }
                except Exception as e:
                    logger.warning(f"get_ltp failed: {e}")
            
            # Try get_market_data as fallback
            if hasattr(client, 'get_market_data'):
                try:
                    response = client.get_market_data(exchange, [token])
                    logger.info(f"get_market_data response: {response}")
                    if response and isinstance(response, list) and len(response) > 0:
                        price = float(response[0].get('ltp', 0))
                        if price > 0:
                            return {
                                "market": market,
                                "symbol": symbol,
                                "price": price,
                                "timestamp": datetime.now(),
                                "volume": response[0].get('volume', 0),
                                "market_open": True,
                                "data_source": "angel_one"
                            }
                except Exception as e:
                    logger.warning(f"get_market_data failed: {e}")
            
        except Exception as e:
            logger.warning(f"Angel One API error for {market}: {e}")
    
    # Fallback: Return default data
    logger.warning(f"Using fallback data for {market}")
    base_price = 25000 if market == "NIFTY" else 85000
    return {
        "market": market,
        "symbol": "NSEI" if market == "NIFTY" else "BSESN",
        "price": base_price,
        "timestamp": datetime.now(),
        "volume": 100000,
        "market_open": True,
        "data_source": "fallback"
    }


def get_market_snapshot_old(market: str = "NIFTY") -> Dict:
    """Legacy function for backward compatibility."""
    return get_market_snapshot(market)


class MarketSnapshot:
    """Market snapshot class for live data."""
    
    def __init__(self, market: str = "NIFTY"):
        self.market = market
        self._data = None
    
    def refresh(self) -> Dict:
        """Refresh market data."""
        self._data = get_market_snapshot(self.market)
        return self._data
    
    def get_data(self) -> Dict:
        """Get current market data."""
        if self._data is None:
            self.refresh()
        return self._data
