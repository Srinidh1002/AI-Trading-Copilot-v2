"""N3 - Decision pipeline trace. READ-ONLY. No trades, no state writes.

Walks the bot's own production decision path:
    connect -> load_instruments -> get_spot -> get_expiry -> get_options
    -> get_enhanced_sentiment -> select_trade
Does NOT call run_single_session. Does NOT write state. Does NOT open WS monitor.
"""
import sys
from datetime import datetime
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot

for market in ("NIFTY", "SENSEX"):
    print("=" * 100)
    print(f"N3 TRACE - {market}   {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 100)

    b = UnifiedTradingBot(market)
    b.connect_with_retry()
    b.load_instruments()

    print(f"\n--- [1] SPOT ---")
    spot = b.get_spot()
    print(f"  spot = {spot}")

    print(f"\n--- [2] EXPIRY ---")
    expiry = b.get_expiry()
    print(f"  expiry = {expiry}")

    print(f"\n--- [3] CHAIN (near-ATM ltp only) ---")
    options, atm = b.get_options(spot, expiry)
    print(f"  atm = {atm}   options_returned = {len(options)}")

    print(f"\n--- [4] ENHANCED SENTIMENT (full pipeline) ---")
    sentiment = b.get_enhanced_sentiment(spot, options)
    print(f"  >>> sentiment = {sentiment}")
    print(f"  >>> decision_state = {getattr(b, 'decision_state', 'N/A')}")

    print(f"\n--- [5] SELECT TRADE ---")
    trade = b.select_trade(sentiment, spot, options)
    if trade:
        print(f"  >>> SELECTED: {trade.get('type')} {trade.get('strike')} "
              f"signal={trade.get('signal')} ltp={trade.get('entry')} "
              f"bid={trade.get('bid')} ask={trade.get('ask')} "
              f"score={trade.get('rank_score')}")
    else:
        print(f"  >>> NO_TRADE (select_trade returned None)")
        print(f"  >>> decision_state = {getattr(b, 'decision_state', 'N/A')}")

    print()
