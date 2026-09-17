"""
Live Paper Trading Runner
Runs the paper trading engine with live market data during market hours.
PAPER ONLY - NO BROKER ORDERS
"""

import time
import logging
from datetime import datetime, time as dt_time
from services.trading.paper_engine import PaperTradingEngine
from services.certification.runner import CertificationRunner


# Market hours (India Standard Time)
MARKET_OPEN = dt_time(9, 15)   # 9:15 AM
MARKET_CLOSE = dt_time(15, 30)  # 3:30 PM


def is_market_hours() -> bool:
    """Check if currently within market hours."""
    now = datetime.now().time()
    # Check if between 9:15 AM and 3:30 PM
    if now >= MARKET_OPEN and now <= MARKET_CLOSE:
        return True
    return False


def run_live_paper_trading():
    """Run live paper trading during market hours."""
    print("=" * 60)
    print("LIVE PAPER TRADING")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("PAPER ONLY - NO BROKER ORDERS")
    print("Market hours: 9:15 AM - 3:30 PM IST")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    # Initialize paper trading engine with live mode
    engine = PaperTradingEngine({
        "mode": "paper",  # LIVE mode
        "markets": ["NIFTY", "SENSEX"],
        "days": 1,
        "max_open_trades": 1,
        "pipeline_config": {
            "min_confidence": 50,  # Lowered for live testing
            "min_risk_reward": 1.0,
            "min_technical_score": 40,
            "min_options_score": 40,
        }
    })
    
    logger.info("Paper trading engine initialized in LIVE mode")
    logger.info("Starting live paper trading loop...")
    
    # Trade counter
    trade_count = 0
    
    try:
        while True:
            # Check market hours
            if not is_market_hours():
                logger.info("Market closed. Waiting for market hours...")
                # Wait and check again
                time.sleep(60)
                continue
            
            # Run one cycle
            logger.info(f"Cycle {trade_count + 1} - Running live analysis...")
            
            # Get market data and make decisions
            results = engine.run()
            
            # Log results
            for market, stats in results.items():
                trades = stats.get("total_trades", 0)
                if trades > 0:
                    trade_count += trades
                    logger.info(f"{market}: {trades} new trades (total: {trade_count})")
                    
                    # Show trade details
                    active_trades = engine.get_active_trades()
                    for trade in active_trades:
                        logger.info(f"  Active: {trade.market} {trade.direction} @ {trade.entry_price:.2f}")
                        logger.info(f"    Targets: T1={trade.target1:.2f}, T2={trade.target2:.2f}, T3={trade.target3:.2f}")
                        logger.info(f"    Stop: {trade.stop_loss:.2f}")
            
            # Show certification status
            cert = CertificationRunner({"target_trades": 100})
            for market in ["NIFTY", "SENSEX"]:
                stats = cert.get_stats(market)
                if stats:
                    logger.info(f"Certification {market}: {stats.countable_trades}/{stats.target_trades}")
            
            # Wait before next cycle (5-10 seconds)
            time.sleep(5)
            
    except KeyboardInterrupt:
        logger.info("=" * 60)
        logger.info("LIVE PAPER TRADING STOPPED")
        logger.info(f"Total trades: {trade_count}")
        logger.info(f"Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Error in live paper trading: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_live_paper_trading()
