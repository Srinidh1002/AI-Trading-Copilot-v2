# test_premium_trade.py
# Standalone test for premium-based trading

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import logging
from services.trading.advanced_paper_engine import AdvancedPaperTradingEngine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_premium_trading():
    """Test premium-based trading with forced trades."""
    
    print("=" * 60)
    print("🧪 TEST: Premium-Based Trading")
    print("=" * 60)
    
    # Create engine with ₹10,00,000 capital
    engine = AdvancedPaperTradingEngine(capital=1000000, max_positions=2)
    await engine.start()
    
    # Test NIFTY trade
    nifty_ltp = 23866.0
    logger.info(f"\n📊 Testing NIFTY @ {nifty_ltp:.2f}")
    
    nifty_premium = engine.get_option_premium('NIFTY', nifty_ltp, 'CALL')
    logger.info(f"   Premium: ₹{nifty_premium:.2f}")
    
    size = engine.calculate_position_size(nifty_premium, 'NIFTY')
    logger.info(f"   Lots: {size['lots']}, Quantity: {size['quantity']}")
    logger.info(f"   Deployed: ₹{size['deployed']:,.2f} ({size['deployed']/1000000*100:.1f}% of capital)")
    
    # Force a trade
    tick_data = {'symbol': 'NIFTY', 'ltp': nifty_ltp}
    signal = await engine.analyze_signal(tick_data)
    
    if signal:
        logger.info(f"   ✅ Signal generated: {signal['signal']}")
        position = engine._enter_option_position(tick_data, 'CALL', signal, {})
        logger.info(f"   ✅ Position entered: {position['symbol']} @ ₹{position['entry_price']:.2f}")
        logger.info(f"      Underlying: ₹{position['underlying_price']:.2f}")
    else:
        logger.warning("   ❌ No signal generated - forcing trade")
        # Force a trade manually
        position = engine._enter_option_position(
            tick_data, 
            'CALL', 
            {
                'symbol': 'NIFTY',
                'option_type': 'CALL',
                'strike': 23900,
                'entry_premium': nifty_premium,
                'lots': 1,
                'reason': 'Forced test trade',
                'regime': 'NEUTRAL',
                'confidence': 0.80
            },
            {}
        )
        logger.info(f"   ✅ Force trade entered: {position['symbol']} @ ₹{position['entry_price']:.2f}")
    
    # Test SENSEX trade
    sensex_ltp = 76408.96
    logger.info(f"\n📊 Testing SENSEX @ {sensex_ltp:.2f}")
    
    sensex_premium = engine.get_option_premium('SENSEX', sensex_ltp, 'CALL')
    logger.info(f"   Premium: ₹{sensex_premium:.2f}")
    
    size = engine.calculate_position_size(sensex_premium, 'SENSEX')
    logger.info(f"   Lots: {size['lots']}, Quantity: {size['quantity']}")
    logger.info(f"   Deployed: ₹{size['deployed']:,.2f} ({size['deployed']/1000000*100:.1f}% of capital)")
    
    # Force SENSEX trade
    tick_data = {'symbol': 'SENSEX', 'ltp': sensex_ltp}
    signal = await engine.analyze_signal(tick_data)
    
    if signal:
        logger.info(f"   ✅ Signal generated: {signal['signal']}")
        position = engine._enter_option_position(tick_data, 'CALL', signal, {})
        logger.info(f"   ✅ Position entered: {position['symbol']} @ ₹{position['entry_price']:.2f}")
    else:
        logger.warning("   ❌ No signal generated - forcing trade")
        position = engine._enter_option_position(
            tick_data, 
            'CALL', 
            {
                'symbol': 'SENSEX',
                'option_type': 'CALL',
                'strike': 76400,
                'entry_premium': sensex_premium,
                'lots': 1,
                'reason': 'Forced test trade',
                'regime': 'NEUTRAL',
                'confidence': 0.80
            },
            {}
        )
        logger.info(f"   ✅ Force trade entered: {position['symbol']} @ ₹{position['entry_price']:.2f}")
    
    # Show summary
    stats = engine.get_stats()
    print("\n" + "=" * 60)
    print("📊 TRADING SUMMARY")
    print("=" * 60)
    print(f"Total Positions: {stats['total_positions']}")
    print(f"Open Positions: {stats['open_positions']}")
    print(f"Total Deployed: ₹{stats['total_deployed']:,.2f}")
    print(f"Usage: {stats['usage_percent']:.1f}%")
    print(f"Available Capital: ₹{stats['available_capital']:,.2f}")
    print("\nPOSITIONS:")
    for pos in stats['positions']:
        if pos.get('status') == 'OPEN':
            print(f"  {pos['symbol']} {pos['option_type']} @ ₹{pos['entry_price']:.2f}")
            print(f"    Lots: {pos['lots']}, Quantity: {pos['quantity']}")
            print(f"    Deployed: ₹{pos['deployed_capital']:,.2f}")
            print(f"    Underlying: ₹{pos['underlying_price']:.2f}")
    print("=" * 60)
    
    await engine.stop()

if __name__ == "__main__":
    asyncio.run(test_premium_trading())
