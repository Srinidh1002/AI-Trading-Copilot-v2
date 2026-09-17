"""
Auto Trade Scheduler - Automatically starts at 9:15 AM
Checks all engines at 9:00 AM, starts trading at 9:15 AM
"""

import time
import logging
import subprocess
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Times
CHECK_TIME = dt_time(9, 0)    # 9:00 AM - Check all engines
START_TIME = dt_time(9, 15)   # 9:15 AM - Start trading
END_TIME = dt_time(15, 40)    # 3:40 PM - Stop trading


def check_all_engines():
    """Check all engines are ready."""
    logger.info("=" * 60)
    logger.info("🔍 CHECKING ALL ENGINES")
    logger.info("=" * 60)
    
    checks = []
    
    # 1. Check Angel One connection
    try:
        from services.broker.angel_client import AngelMarketDataClient
        client = AngelMarketDataClient()
        client.login()
        checks.append(("Angel One", True, "Connected"))
    except Exception as e:
        checks.append(("Angel One", False, str(e)))
    
    # 2. Check Market Data
    try:
        from services.market.market_snapshot import get_market_snapshot
        data = get_market_snapshot("NIFTY")
        if data and data.get("price", 0) > 0:
            checks.append(("Market Data", True, f"Price: {data.get('price', 0)}"))
        else:
            checks.append(("Market Data", False, "No data"))
    except Exception as e:
        checks.append(("Market Data", False, str(e)))
    
    # 3. Check Decision Pipeline
    try:
        from services.decision.pipeline import DecisionPipeline
        pipeline = DecisionPipeline()
        checks.append(("Decision Pipeline", True, "Ready"))
    except Exception as e:
        checks.append(("Decision Pipeline", False, str(e)))
    
    # 4. Check Pre-Market Intelligence
    try:
        from services.analysis.pre_market_intelligence import analyze_pre_market
        pre_market = analyze_pre_market({})
        checks.append(("Pre-Market Engine", True, f"Score: {pre_market.get('overall_score', 50)}"))
    except Exception as e:
        checks.append(("Pre-Market Engine", False, str(e)))
    
    # 5. Check Market Comparison
    try:
        from services.decision.market_comparison import compare_markets_full
        checks.append(("Market Comparison", True, "Ready"))
    except Exception as e:
        checks.append(("Market Comparison", False, str(e)))
    
    # 6. Check Certification Engine
    try:
        from services.certification.certification_engine import CertificationEngine
        cert = CertificationEngine({"markets": ["NIFTY", "SENSEX"]})
        checks.append(("Certification", True, "Ready"))
    except Exception as e:
        checks.append(("Certification", False, str(e)))
    
    # Print results
    all_ready = True
    for name, status, detail in checks:
        icon = "✅" if status else "❌"
        logger.info(f"  {icon} {name}: {detail}")
        if not status:
            all_ready = False
    
    logger.info("=" * 60)
    
    if all_ready:
        logger.info("✅ ALL ENGINES READY - Starting at 9:15 AM")
    else:
        logger.warning("⚠️ SOME ENGINES FAILED - Proceeding anyway")
    
    return all_ready


def run_paper_trading():
    """Run the paper trading script."""
    logger.info("=" * 60)
    logger.info("🚀 STARTING PAPER TRADING")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Run the trading script
    script_path = Path(__file__).parent / "live_paper_trading_fixed.py"
    
    try:
        subprocess.run([sys.executable, str(script_path)], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Trading script failed: {e}")
    except KeyboardInterrupt:
        logger.info("Manual stop requested")


def is_market_open() -> bool:
    """Check if market is currently open."""
    now = datetime.now().time()
    return START_TIME <= now <= END_TIME


def wait_until(target_time: dt_time):
    """Wait until a specific time."""
    now = datetime.now()
    target = datetime.combine(now.date(), target_time)
    
    # If the target time is already past, add a day
    if target <= now:
        target = target + timedelta(days=1)
    
    wait_seconds = (target - now).total_seconds()
    if wait_seconds > 0:
        logger.info(f"⏳ Waiting until {target_time.strftime('%H:%M')} ({wait_seconds/60:.1f} minutes)")
        time.sleep(wait_seconds)


def main():
    """Main auto-scheduler."""
    logger.info("=" * 60)
    logger.info("🤖 AI TRADING COPILOT - AUTO SCHEDULER")
    logger.info("=" * 60)
    logger.info(f"Check time: {CHECK_TIME.strftime('%H:%M')}")
    logger.info(f"Start time: {START_TIME.strftime('%H:%M')}")
    logger.info(f"End time: {END_TIME.strftime('%H:%M')}")
    logger.info("=" * 60)
    
    # Wait until 9:00 AM
    wait_until(CHECK_TIME)
    
    # Check all engines
    all_ready = check_all_engines()
    
    # Wait until 9:15 AM
    wait_until(START_TIME)
    
    # Run trading
    run_paper_trading()


if __name__ == "__main__":
    main()
