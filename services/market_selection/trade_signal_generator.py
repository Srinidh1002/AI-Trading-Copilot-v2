# services/market_selection/trade_signal_generator.py

import logging
from typing import Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class TradeSignalGenerator:
    """Generates final trade signals with WAIT/NO TRADE recommendations"""
    
    def __init__(self):
        self.current_signal = {
            'signal': 'WAIT',
            'reason': 'Initializing...',
            'timestamp': datetime.now().isoformat()
        }
        
    async def generate_signal(self, market_context: Dict, market_comparison: Dict, option_selection: Dict) -> Dict:
        """Generate final trade signal"""
        
        signal = {
            'signal': 'WAIT',
            'market': 'NONE',
            'option_type': 'NONE',
            'entry_price': 0,
            'stop_loss': 0,
            'targets': {'T1': 0, 'T2': 0, 'T3': 0},
            'reason': '',
            'confidence': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        # Check if market is open
        current_time = datetime.now().time()
        market_open = current_time >= datetime.strptime('09:15', '%H:%M').time()
        market_close = current_time <= datetime.strptime('15:30', '%H:%M').time()
        
        if not market_open or not market_close:
            signal['signal'] = 'WAIT'
            signal['reason'] = 'Market is closed'
            self.current_signal = signal
            return signal
        
        # Get market bias
        market_bias = market_context.get('market_bias', 'NEUTRAL')
        
        # Check if market is too volatile
        volatility = market_context.get('volatility_level', 'MEDIUM')
        if volatility == 'HIGH':
            signal['signal'] = 'WAIT'
            signal['reason'] = 'High volatility - waiting for stability'
            self.current_signal = signal
            return signal
        
        # Check recommendation
        recommendation = market_comparison.get('recommendation', 'WAIT')
        if recommendation == 'WAIT':
            signal['signal'] = 'WAIT'
            signal['reason'] = market_comparison.get('reason', 'No clear market advantage')
            self.current_signal = signal
            return signal
        
        # Check option selection
        option_type = option_selection.get('option_type', 'WAIT')
        confidence = option_selection.get('confidence', 0)
        
        if option_type == 'WAIT' or confidence < 0.6:
            signal['signal'] = 'WAIT'
            signal['reason'] = option_selection.get('reason', 'Option signal too weak')
            self.current_signal = signal
            return signal
        
        # Generate final signal
        signal['signal'] = 'TRADE'
        signal['market'] = recommendation
        signal['option_type'] = option_type
        signal['entry_price'] = option_selection.get('entry_price', 0)
        signal['stop_loss'] = option_selection.get('stop_loss', 0)
        signal['targets'] = option_selection.get('targets', {'T1': 0, 'T2': 0, 'T3': 0})
        signal['confidence'] = confidence
        signal['reason'] = f"Strong {option_type} signal on {recommendation} (Confidence: {confidence:.2f})"
        
        self.current_signal = signal
        logger.info(f"📊 TRADE SIGNAL: {signal['signal']} - {signal['market']} {signal['option_type']} @ {signal['entry_price']}")
        
        return signal
    
    def get_current_signal(self) -> Dict:
        """Get the latest trade signal"""
        return self.current_signal
