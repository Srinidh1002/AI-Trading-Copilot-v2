# services/market_selection/market_comparator.py

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketComparator:
    """Compares NIFTY vs SENSEX to recommend best trade"""
    
    def __init__(self):
        self.comparison_result = {}
        
    async def compare_markets(self, context: Dict, price_data: Dict) -> Dict:
        """Compare NIFTY and SENSEX and recommend which to trade"""
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'recommendation': 'WAIT',
            'nifty_score': 0,
            'sensex_score': 0,
            'reason': '',
            'trade_signal': 'WAIT'
        }
        
        # Get data for both indices
        nifty = context.get('previous_session', {}).get('nifty', {})
        sensex = context.get('previous_session', {}).get('sensex', {})
        
        # Score calculation
        nifty_score = self._calculate_market_score(nifty, 'NIFTY', context)
        sensex_score = self._calculate_market_score(sensex, 'SENSEX', context)
        
        result['nifty_score'] = nifty_score
        result['sensex_score'] = sensex_score
        
        # Determine recommendation
        if nifty_score > sensex_score and nifty_score > 0.5:
            result['recommendation'] = 'NIFTY'
            result['trade_signal'] = 'BUY_CALL' if nifty_score > 0.7 else 'WAIT'
            result['reason'] = f'NIFTY has stronger setup (score: {nifty_score:.2f} vs {sensex_score:.2f})'
        elif sensex_score > nifty_score and sensex_score > 0.5:
            result['recommendation'] = 'SENSEX'
            result['trade_signal'] = 'BUY_CALL' if sensex_score > 0.7 else 'WAIT'
            result['reason'] = f'SENSEX has stronger setup (score: {sensex_score:.2f} vs {nifty_score:.2f})'
        elif nifty_score > 0.3 and sensex_score > 0.3:
            result['recommendation'] = 'BOTH'
            result['trade_signal'] = 'BUY_CALL'
            result['reason'] = 'Both markets show positive setup'
        else:
            result['recommendation'] = 'WAIT'
            result['trade_signal'] = 'WAIT'
            result['reason'] = 'No clear market advantage'
        
        self.comparison_result = result
        logger.info(f"📊 Market Comparison: {result['recommendation']} - {result['reason']}")
        
        return result
    
    def _calculate_market_score(self, market_data: Dict, symbol: str, context: Dict) -> float:
        """Calculate score for a market (0-1)"""
        score = 0.5  # Neutral base
        
        # 1. Price action (0.3 weight)
        change_percent = market_data.get('change_percent', 0)
        if change_percent > 0:
            score += min(change_percent / 2, 0.3)
        else:
            score -= min(abs(change_percent) / 2, 0.3)
        
        # 2. Volume (0.1 weight)
        volume = market_data.get('volume', 0)
        if volume > 1000000:
            score += 0.1
        
        # 3. Market bias alignment (0.2 weight)
        market_bias = context.get('market_bias', 'NEUTRAL')
        if market_bias in ['BULLISH', 'STRONGLY_BULLISH']:
            score += 0.2
        elif market_bias in ['BEARISH', 'STRONGLY_BEARISH']:
            score -= 0.2
        
        # 4. Key levels (0.2 weight)
        ltp = market_data.get('close', 0)
        resistance = context.get('previous_session', {}).get('key_levels', {}).get(f'{symbol.lower()}_resistance', 0)
        support = context.get('previous_session', {}).get('key_levels', {}).get(f'{symbol.lower()}_support', 0)
        
        if ltp and resistance and support:
            distance_to_resistance = (resistance - ltp) / ltp * 100
            distance_to_support = (ltp - support) / ltp * 100
            
            if distance_to_resistance < 1:  # Near resistance
                score -= 0.2
            elif distance_to_support < 1:  # Near support
                score += 0.2
        
        # 5. VIX/Volatility (0.2 weight)
        vix = context.get('vix', {}).get('current', 0)
        if vix < 15:  # Low volatility - stable
            score += 0.2
        elif vix > 25:  # High volatility - risky
            score -= 0.2
        
        # Clamp score between 0 and 1
        return max(0, min(1, score))
    
    def get_recommendation(self) -> Dict:
        """Get the latest recommendation"""
        return self.comparison_result
