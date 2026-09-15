# Add this function to run_historical_test_updated.py before the main loop

def get_premium_for_test(symbol, underlying_price, option_type="CALL"):
    """Get premium for testing purposes."""
    # For NIFTY, premium is roughly 2-5% of underlying
    # For SENSEX, premium is roughly 1-3% of underlying
    if symbol == "NIFTY":
        # NIFTY premium typically ₹100-500 for ATM options
        return round(underlying_price * 0.008, 2)  # ~0.8% of underlying
    else:
        # SENSEX premium typically ₹50-200 for ATM options
        return round(underlying_price * 0.003, 2)  # ~0.3% of underlying

# Then in the entry code, replace:
# entry_price = current_price  # WRONG
# With:
# entry_price = get_premium_for_test(symbol, current_price, option_type)
