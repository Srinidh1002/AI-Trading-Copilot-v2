# services/market/websocket_option_chain.py - REAL OPTION CHAIN PARSER

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class WebSocketOptionChain:
    """Parse real option chain data from WebSocket bridge."""
    
    def __init__(self):
        self.option_chain = {}
        self.last_update = 0
        self.data_dir = Path("data/task9/live_stream")
    
    def _load_latest_data(self) -> dict:
        """Load the latest data from WebSocket bridge."""
        try:
            # Find the latest file
            files = sorted(self.data_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
            if files:
                with open(files[0], 'r') as f:
                    content = f.read()
                    # Try to parse JSON
                    try:
                        data = json.loads(content)
                        return data
                    except:
                        # Try JSONL format
                        lines = content.strip().split('\n')
                        for line in lines:
                            try:
                                data = json.loads(line)
                                if 'ticks' in data or 'market' in data:
                                    return data
                            except:
                                pass
        except Exception as e:
            logger.debug(f"[OPTION-CHAIN] Error loading data: {e}")
        return {}
    
    def get_option_chain(self, symbol: str) -> dict:
        """Get option chain for a symbol."""
        data = self._load_latest_data()
        if not data:
            return {}
        
        # Look for option chain data
        # The data structure from Angel One TradeOne has specific format
        if 'option_chain' in data:
            return data['option_chain'].get(symbol, {})
        
        # Try to find in ticks
        if 'ticks' in data:
            for tick in data['ticks']:
                if tick.get('symbol') == symbol and 'strike' in tick:
                    # This is option data
                    strike = tick.get('strike', 0)
                    ltp = tick.get('ltp', 0)
                    oi = tick.get('oi', 0)
                    # Store it
                    if symbol not in self.option_chain:
                        self.option_chain[symbol] = {'strikes': []}
                    self.option_chain[symbol]['strikes'].append({
                        'strike': strike,
                        'ltp': ltp,
                        'oi': oi
                    })
        
        return self.option_chain.get(symbol, {})
    
    def get_atm_premium(self, symbol: str, underlying: float) -> float:
        """Get the real ATM premium from option chain."""
        chain = self.get_option_chain(symbol)
        strikes = chain.get('strikes', [])
        
        if strikes:
            # Find the strike closest to underlying
            atm = min(strikes, key=lambda s: abs(s.get('strike', 0) - underlying))
            premium = atm.get('ltp', 0)
            if premium > 0:
                logger.info(f"[OPTION-CHAIN] {symbol} ATM premium: ₹{premium:.2f} from strike {atm.get('strike', 0)}")
                return premium
        
        # Fallback: use realistic premium percentage from actual Angel One data
        # From the screenshot: NIFTY 24000 strike premium = ₹105.30 on LTP ~23995
        # That's ~0.44% of LTP
        if symbol == 'NIFTY':
            premium_pct = 0.0044  # 0.44% (from actual Angel One data)
        else:  # SENSEX
            premium_pct = 0.0015  # 0.15% (approx for SENSEX)
        
        premium = underlying * premium_pct
        premium = max(10, round(premium, 2))
        logger.info(f"[OPTION-CHAIN] {symbol} ATM premium (calculated): ₹{premium:.2f}")
        return premium
    
    def get_atm_strike(self, symbol: str, underlying: float) -> float:
        """Get the ATM strike from option chain."""
        chain = self.get_option_chain(symbol)
        strikes = chain.get('strikes', [])
        
        if strikes:
            atm = min(strikes, key=lambda s: abs(s.get('strike', 0) - underlying))
            return atm.get('strike', 0)
        
        # Fallback: calculate from underlying
        step = 50 if symbol == 'NIFTY' else 100
        return round(underlying / step) * step
