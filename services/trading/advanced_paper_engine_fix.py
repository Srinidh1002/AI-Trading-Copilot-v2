# services/trading/advanced_paper_engine.py
# FIXED: Regime-aware signal generation

async def _generate_trade_signal(self, latest_data: dict):
    """Generate trade signal with REGIME AWARENESS - FIXED LOGIC"""
    
    for symbol in ['NIFTY', 'SENSEX']:
        # Check max positions
        active_positions = self._get_active_positions(symbol)
        if len(active_positions) >= self.max_positions_per_market:
            continue
        
        tick_data = latest_data.get(symbol)
        if not tick_data:
            continue
        
        ltp = tick_data['ltp']
        history = self.price_history.get(symbol, [])
        if len(history) < 30:
            continue
        
        # Get regime
        regime = self.current_regime.get(symbol, {'regime': 'NEUTRAL', 'trend': 'NEUTRAL'})
        market_bias = self.market_context.get('market_bias', 'NEUTRAL')
        
        # Get indicators
        rsi = self.indicators.get(f'{symbol}_RSI', 50)
        sma_5 = self.indicators.get(f'{symbol}_SMA_5', ltp)
        sma_10 = self.indicators.get(f'{symbol}_SMA_10', ltp)
        sma_20 = self.indicators.get(f'{symbol}_SMA_20', ltp)
        
        option_type = None
        confidence = 0
        reason = ""
        
        # ============================================================
        # STRATEGY 1: REGIME-AWARE LOGIC (FIXED)
        # ============================================================
        
        # IMPORTANT: If market is CONSOLIDATION, DO NOT use market bias!
        # Only use breakout or RSI strategies
        if regime['regime'] == 'CONSOLIDATION':
            # Calculate consolidation range
            recent_high = max(history[-20:])
            recent_low = min(history[-20:])
            range_size = recent_high - recent_low
            range_percent = (range_size / ltp) * 100 if ltp > 0 else 0
            
            # Breakout detection (REAL breakout, not just bias)
            if ltp > recent_high * 0.998 and range_percent > 0.2:
                option_type = 'CALL'
                confidence = 0.65
                reason = f"Breakout above consolidation {range_percent:.2f}% range"
            elif ltp < recent_low * 1.002 and range_percent > 0.2:
                option_type = 'PUT'
                confidence = 0.65
                reason = f"Breakout below consolidation {range_percent:.2f}% range"
            elif rsi > 70:
                option_type = 'PUT'  # Overbought in consolidation
                confidence = 0.55
                reason = f"Overbought consolidation | RSI={rsi:.1f}"
            elif rsi < 30:
                option_type = 'CALL'  # Oversold in consolidation
                confidence = 0.55
                reason = f"Oversold consolidation | RSI={rsi:.1f}"
            else:
                # NO ENTRY in consolidation without breakout!
                # This is the CRITICAL FIX - don't use STRONGLY_BULLISH in consolidation
                option_type = None
                confidence = 0
                reason = f"Consolidation - waiting for breakout"
        
        # ============================================================
        # STRATEGY 2: TRENDING MARKET (Use SMA + RSI)
        # ============================================================
        elif regime['regime'] == 'TRENDING':
            if ltp > sma_5 > sma_10 > sma_20 and rsi > 50:
                option_type = 'CALL'
                confidence = 0.75
                reason = f"Strong uptrend | RSI={rsi:.1f}"
            elif ltp < sma_5 < sma_10 < sma_20 and rsi < 50:
                option_type = 'PUT'
                confidence = 0.75
                reason = f"Strong downtrend | RSI={rsi:.1f}"
            else:
                option_type = None
                confidence = 0
                reason = f"Neutral trend"
        
        # ============================================================
        # STRATEGY 3: NEUTRAL REGIME (Use market bias ONLY if clear)
        # ============================================================
        elif regime['regime'] == 'NEUTRAL':
            # Only use market bias if it's VERY strong
            if market_bias in ['STRONGLY_BULLISH', 'BULLISH'] and rsi > 40:
                option_type = 'CALL'
                confidence = 0.50
                reason = f"Neutral regime with bullish bias: {market_bias}"
            elif market_bias in ['STRONGLY_BEARISH', 'BEARISH'] and rsi < 60:
                option_type = 'PUT'
                confidence = 0.50
                reason = f"Neutral regime with bearish bias: {market_bias}"
            else:
                option_type = None
                confidence = 0
                reason = f"Neutral regime - no clear signal"
        
        # ============================================================
        # ENTRY EXECUTION (Only if confidence > 0.50)
        # ============================================================
        if option_type and confidence >= 0.50:
            # DO NOT enter if in consolidation AND no breakout!
            if regime['regime'] == 'CONSOLIDATION':
                # Double-check: only enter on breakout in consolidation
                if 'Breakout' not in reason and 'overbought' not in reason and 'oversold' not in reason:
                    option_type = None
                    confidence = 0
                    reason = "Consolidation - breakout required for entry"
            
            if option_type and confidence >= 0.50:
                entry_price = ltp
                stop_loss = entry_price * (1 - 0.005) if option_type == 'CALL' else entry_price * (1 + 0.005)
                
                self.current_signal = {
                    'signal': 'TRADE',
                    'market': symbol,
                    'option_type': option_type,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'targets': {
                        'T1': entry_price * (1 + (self.T1/100)) if option_type == 'CALL' else entry_price * (1 - (self.T1/100)),
                        'T2': entry_price * (1 + (self.T2/100)) if option_type == 'CALL' else entry_price * (1 - (self.T2/100)),
                        'T3': entry_price * (1 + (self.T3/100)) if option_type == 'CALL' else entry_price * (1 - (self.T3/100))
                    },
                    'confidence': confidence,
                    'reason': reason,
                    'regime': regime['regime']
                }
                
                self.dashboard.add_trade_signal(self.current_signal)
                
                position_size = self.deployment_manager.get_position_size(
                    symbol, entry_price, stop_loss
                )
                
                await self._enter_option_position(
                    tick_data, option_type, self.current_signal, position_size
                )
                return
            else:
                # No entry - set WAIT signal
                self.current_signal = {
                    'signal': 'WAIT',
                    'market': symbol,
                    'option_type': 'NONE',
                    'entry_price': 0,
                    'stop_loss': 0,
                    'targets': {'T1': 0, 'T2': 0, 'T3': 0},
                    'confidence': confidence,
                    'reason': reason,
                    'regime': regime['regime']
                }
                self.dashboard.add_trade_signal(self.current_signal)
                return
