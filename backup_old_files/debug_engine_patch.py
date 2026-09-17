# Add this method to advanced_paper_engine.py after the analyze_signal method

    async def analyze_signal(self, tick_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze market data and generate trading signal."""
        symbol = tick_data.get('symbol', 'NIFTY')
        ltp = tick_data.get('ltp', 0)
        
        if ltp <= 0:
            logger.debug(f"[DEBUG] No LTP for {symbol}")
            return None
        
        # Get option premium
        premium = self.get_option_premium(symbol, ltp, 'CALL')
        strike = self.get_strike_from_underlying(ltp, symbol)
        
        logger.info(f"[DEBUG] {symbol}: LTP={ltp:.2f}, Premium={premium:.2f}, Strike={strike:.0f}")
        
        # Check if we can afford it
        size = self.calculate_position_size(premium, symbol)
        logger.info(f"[DEBUG] Position size: lots={size['lots']}, deployed=₹{size['deployed']:,.2f}")
        
        if size['lots'] <= 0:
            logger.warning(f"[DEBUG] Cannot afford {symbol}: need ₹{size['deployed']:,.2f}, have ₹{self.capital:,.2f}")
            return None
        
        # Generate signal
        confidence = 0.55
        reason = "Neutral with bullish bias"
        
        if confidence >= 0.50 and size['lots'] > 0:
            signal = {
                'signal': 'TRADE',
                'symbol': symbol,
                'option_type': 'CALL',
                'strike': strike,
                'underlying_price': ltp,
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
                'confidence': confidence,
                'reason': reason,
                'regime': self.regime,
                'timestamp': datetime.now().isoformat()
            }
            logger.info(f"[SIGNAL] TRADE {symbol} CALL @ ₹{premium:.2f} premium")
            return signal
        
        logger.info(f"[DEBUG] No signal for {symbol}: confidence={confidence}")
        return None
