# Add this debug code to run_advanced_trading.py in the run_trading_loop method

# After getting market_data, add:
if self.cycle_count % 5 == 0:
    logger.info(f"[DEBUG] Market data: {list(market_data.keys())}")
    if market_data:
        for symbol, data in market_data.items():
            logger.info(f"[DEBUG] {symbol}: LTP={data.get('ltp', 0)}")

# If still no data after 10 cycles, generate synthetic data for testing
if self.cycle_count > 10 and not market_data:
    logger.warning("[DEBUG] No market data - generating synthetic data for testing")
    base_prices = {'NIFTY': 23864.55, 'SENSEX': 76413.50}
    for symbol in ['NIFTY', 'SENSEX']:
        import random
        variation = random.uniform(-10, 10)
        market_data[symbol] = {
            'ltp': base_prices[symbol] + variation,
            'timestamp': datetime.now().isoformat()
        }
