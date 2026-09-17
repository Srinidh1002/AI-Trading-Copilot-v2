# services/market_selection/option_selector.py

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class OptionSelector:
    """Selects CALL or PUT options based on market analysis"""
    
    def __init__(self):
        self.selected_option = {}
        
    async def select_option(self, market_data: Dict, context: Dict) -> Dict:
        """Select whether to buy CALL or PUT"""
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'option_type': 'WAIT',
            'confidence': 0,
            'entry_price': 0,
            'stop_loss': 0,
            'targets': {'T1': 0, 'T2': 0, 'T3': 0},
            'reason': ''
        }
        
        # Get current price
        ltp = market_data.get('ltp', 0)
        if not ltp:
            result['reason'] = 'No price data available'
            return result
        
        # Get indicators
        rsi = context.get('indicators', {}).get('RSI', 50)
        macd = context.get('indicators', {}).get('MACD', 0)
        sma_5 = context.get('indicators', {}).get('SMA_5', ltp)
        sma_10 = context.get('indicators', {}).get('SMA_10', ltp)
        sma_20 = context.get('indicators', {}).get('SMA_20', ltp)
        sma_50 = context.get('indicators', {}).get('SMA_50', ltp)
        
        # Determine trend
        bull_trend = ltp > sma_5 > sma_10 > sma_20 > sma_50
        bear_trend = ltp < sma_5 < sma_10 < sma_20 < sma_50
        
        # Determine overbought/oversold
        overbought = rsi > 70
        oversold = rsi < 30
        
        # Market bias
        market_bias = context.get('market_bias', 'NEUTRAL')
        
        # Select option
        confidence = 0.5
        
        if bull_trend and not overbought and market_bias not in ['BEARISH', 'STRONGLY_BEARISH']:
            option_type = 'CALL'
            confidence = 0.7 + (0.1 if rsi < 60 else 0)
            
            # Add macd confirmation
            if macd > 0:
                confidence += 0.1
            
            # Add market bias confirmation
            if market_bias in ['BULLISH', 'STRONGLY_BULLISH']:
                confidence += 0.1
            
            # Calculate targets
            T1 = ltp * 1.0015  # 0.15%
            T2 = ltp * 1.0030  # 0.30%
            T3 = ltp * 1.0050  # 0.50%
            stop_loss = ltp * 0.9950  # -0.50%
            
            result['option_type'] = 'CALL'
            result['reason'] = f'Strong uptrend with RSI={rsi:.1f}, MACD={macd:.2f}'
            
        elif bear_trend and not overbought and market_bias not in ['BULLISH', 'STRONGLY_BULLISH']:
            option_type = 'PUT'
            confidence = 0.7 + (0.1 if rsi > 40 else 0)
            
            if macd < 0:
                confidence += 0.1
            
            if market_bias in ['BEARISH', 'STRONGLY_BEARISH']:
                confidence += 0.1
            
            T1 = ltp * 0.9985  # -0.15%
            T2 = ltp * 0.9970  # -0.30%
            T3 = ltp * 0.9950  # -0.50%
            stop_loss = ltp * 1.0050  # +0.50%
            
            result['option_type'] = 'PUT'
            result['reason'] = f'Strong downtrend with RSI={rsi:.1f}, MACD={macd:.2f}'
            
        else:
            result['option_type'] = 'WAIT'
            result['reason'] = 'No clear directional bias'
            result['confidence'] = 0
            return result
        
        # If confidence too low, wait
        if confidence < 0.6:
            result['option_type'] = 'WAIT'
            result['reason'] = f'Confidence too low ({confidence:.2f})'
            result['confidence'] = confidence
            return result
        
        result['confidence'] = min(confidence, 1.0)
        result['entry_price'] = ltp
        result['stop_loss'] = stop_loss
        result['targets'] = {'T1': T1, 'T2': T2, 'T3': T3}
        
        self.selected_option = result
        logger.info(f"🎯 Option Selected: {result['option_type']} with confidence {result['confidence']:.2f}")
        
        return result
    
    def get_selected_option(self) -> Dict:
        """Get the latest selected option"""
        return self.selected_option
