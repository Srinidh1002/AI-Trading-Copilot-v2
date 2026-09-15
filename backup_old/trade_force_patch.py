# Add this to run_advanced_trading.py - Force trades for testing

# In the run_trading_loop method, after getting market_data, add:
# If no trades are happening after 10 cycles, force a trade

if self.cycle_count > 10 and len(self.engine.positions) == 0:
    # Force a trade for testing
    for symbol in ['NIFTY', 'SENSEX']:
        if symbol in market_data:
            tick = market_data[symbol]
            ltp = tick.get('ltp', 0)
            if ltp > 0:
                # Force trade
                signal = {
                    'signal': 'TRADE',
                    'symbol': symbol,
                    'option_type': 'CALL',
                    'entry_premium': self.engine.get_option_premium(symbol, ltp, 'CALL'),
                    'lots': 1,
                    'reason': 'FORCED TRADE - Testing',
                    'regime': 'NEUTRAL',
                    'confidence': 0.80
                }
                position = self.engine._enter_option_position(
                    {'symbol': symbol, 'ltp': ltp},
                    'CALL',
                    signal,
                    {}
                )
                if position:
                    logger.info(f"[FORCE] {symbol} CALL @ ₹{position['entry_price']:.2f} premium")
                    break
