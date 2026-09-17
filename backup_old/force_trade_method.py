# Add this method to advanced_paper_engine.py after __init__

    def force_trade(self, symbol: str = "NIFTY", underlying_price: float = None):
        """Force a trade for testing purposes."""
        if underlying_price is None:
            # Get from bridge if available
            if self.bridge and hasattr(self.bridge, 'get_latest_data'):
                data = self.bridge.get_latest_data()
                if data and symbol in data:
                    underlying_price = data[symbol].get('ltp', 0)
            if underlying_price is None or underlying_price == 0:
                underlying_price = 23866.0 if symbol == "NIFTY" else 76408.96
        
        # Get premium
        premium = self.get_option_premium(symbol, underlying_price, 'CALL')
        strike = self.get_strike_from_underlying(underlying_price, symbol)
        size = self.calculate_position_size(premium, symbol)
        
        if size['lots'] <= 0:
            logger.warning(f"[FORCE] Cannot afford {symbol}")
            return None
        
        # Create signal with high confidence
        signal = {
            'signal': 'TRADE',
            'symbol': symbol,
            'option_type': 'CALL',
            'strike': strike,
            'underlying_price': underlying_price,
            'entry_price': premium,
            'entry_premium': premium,
            'lots': size['lots'],
            'lot_size': size['lot_size'],
            'quantity': size['quantity'],
            'deployed': size['deployed'],
            'stop_loss': premium * (1 - self.stop_loss_pct),
            'targets': {
                'T1': premium * (1 + self.T1),
                'T2': premium * (1 + self.T2),
                'T3': premium * (1 + self.T3)
            },
            'confidence': 0.80,
            'reason': "FORCE TRADE - TESTING",
            'regime': self.regime,
            'timestamp': datetime.now().isoformat()
        }
        
        # Enter the position
        tick_data = {'symbol': symbol, 'ltp': underlying_price}
        position = self._enter_option_position(tick_data, 'CALL', signal, {})
        logger.info(f"[FORCE] Entered forced trade for {symbol} @ ₹{premium:.2f} premium")
        return position
