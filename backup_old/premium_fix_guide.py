# run_historical_test_updated.py
# FIXED: Use PREMIUM for entry price, NOT underlying

# Add this function to get premium from strike
def get_option_premium(underlying_price, strike, option_type="CALL"):
    """
    Calculate approximate option premium.
    In production, this should come from the API.
    """
    # Simple approximation for testing
    if option_type == "CALL":
        # In-the-money premium = (underlying - strike) + time value
        moneyness = underlying_price - strike
        if moneyness > 0:
            # ITM: intrinsic value + time value (~5% of underlying)
            premium = moneyness + (underlying_price * 0.02)
        else:
            # OTM: only time value
            premium = underlying_price * 0.015
    else:
        # PUT option
        moneyness = strike - underlying_price
        if moneyness > 0:
            premium = moneyness + (underlying_price * 0.02)
        else:
            premium = underlying_price * 0.015
    
    return max(premium, 10)  # Minimum premium of ₹10

# When entering a trade, use premium instead of underlying:
# Before (WRONG):
# entry_price = current_price  # This is the underlying price!

# After (CORRECT):
# strike = get_strike_for_underlying(current_price)  # Nearest strike
# entry_price = get_option_premium(current_price, strike, option_type)
