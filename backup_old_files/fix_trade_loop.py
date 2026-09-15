# Fix for run_advanced_trading.py - Prevent multiple trades

# In the run_trading_loop method, add this check before entering a trade:

# Check if we already have an OPEN position for this symbol
existing_position = next((p for p in self.engine.positions if p.get('symbol') == symbol and p.get('status') == 'OPEN'), None)

if existing_position:
    # Already have a position for this symbol, skip
    continue

# Also add a cooldown period
if hasattr(self, 'last_trade_time') and (datetime.now() - self.last_trade_time).seconds < 15:
    continue
self.last_trade_time = datetime.now()
