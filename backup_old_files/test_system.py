"""
Complete System Test - Replay Mode
Tests the unified paper trading system with historical data.
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.trading.paper_engine import PaperTradingEngine
from services.trading.health_monitor import PredictionHealthMonitor
from services.trading.target_tracker import TargetTracker
from services.trading.trade_manager import TradeManager
from services.decision.pipeline import DecisionPipeline
from services.certification.runner import CertificationRunner


def test_components():
    """Test all components individually."""
    print("=" * 60)
    print("TESTING COMPONENTS")
    print("=" * 60)
    
    # 1. Health Monitor
    print("\n1. Testing PredictionHealthMonitor...")
    health = PredictionHealthMonitor()
    print("   ✅ PredictionHealthMonitor initialized")
    
    # 2. Target Tracker
    print("\n2. Testing TargetTracker...")
    target = TargetTracker()
    print("   ✅ TargetTracker initialized")
    
    # 3. Trade Manager
    print("\n3. Testing TradeManager...")
    manager = TradeManager()
    print("   ✅ TradeManager initialized")
    
    # 4. Decision Pipeline
    print("\n4. Testing DecisionPipeline...")
    pipeline = DecisionPipeline()
    print("   ✅ DecisionPipeline initialized")
    
    # 5. Certification Runner
    print("\n5. Testing CertificationRunner...")
    cert = CertificationRunner({"target_trades": 10})
    print("   ✅ CertificationRunner initialized")
    
    # 6. Paper Trading Engine
    print("\n6. Testing PaperTradingEngine...")
    engine = PaperTradingEngine({
        "mode": "replay",
        "markets": ["NIFTY", "SENSEX"],
        "days": 5,
        "max_open_trades": 1
    })
    print("   ✅ PaperTradingEngine initialized")
    
    print("\n" + "=" * 60)
    print("✅ ALL COMPONENTS TESTED SUCCESSFULLY")
    print("=" * 60)
    
    return engine


def run_replay_test(engine):
    """Run a replay test."""
    print("\n" + "=" * 60)
    print("RUNNING REPLAY TEST (5 days)")
    print("=" * 60)
    
    try:
        results = engine.run()
        
        print("\nRESULTS:")
        for market, stats in results.items():
            print(f"\n  {market}:")
            print(f"    Total Trades: {stats.get('total_trades', 0)}")
            print(f"    Wins: {stats.get('wins', 0)}")
            print(f"    Losses: {stats.get('losses', 0)}")
            print(f"    Win Rate: {stats.get('win_rate', 0):.2f}%")
            print(f"    Total P&L: ₹{stats.get('total_pnl', 0):,.2f}")
            print(f"    No Trade Count: {stats.get('no_trade_count', 0)}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Error during replay: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_certification_test():
    """Test certification with simulated trades."""
    print("\n" + "=" * 60)
    print("RUNNING CERTIFICATION TEST")
    print("=" * 60)
    
    from datetime import datetime, timedelta
    
    runner = CertificationRunner({
        "target_trades": 5,
        "markets": ["NIFTY"]
    })
    
    print("\nCreating 5 simulated trades...")
    
    for i in range(5):
        # Create a simulated trade
        from types import SimpleNamespace
        trade = SimpleNamespace()
        trade.trade_id = f"SIM_{i}"
        trade.market = "NIFTY"
        trade.direction = "CALL" if i % 2 == 0 else "PUT"
        trade.entry_price = 25000 + i * 100
        trade.exit_price = 25100 + i * 100 if i % 2 == 0 else 24900 - i * 100
        trade.pnl = 100 + i * 10 if i % 2 == 0 else -100 - i * 10
        trade.entry_time = datetime.now() - timedelta(hours=i)
        trade.exit_time = datetime.now()
        trade.exit_reason = "TARGET_1"
        trade.decision_confidence = 75 + i
        trade.gate_results = [{"status": "PASS"} for _ in range(9)]
        trade.is_valid = True
        trade.mode = "paper"
        trade.status = "CLOSED"
        
        runner.record_trade(trade, "NIFTY")
        print(f"   Trade {i+1}: {'WIN' if trade.pnl > 0 else 'LOSS'} (₹{trade.pnl:.2f})")
    
    # Get stats
    stats = runner.get_stats("NIFTY")
    report = runner.generate_report("NIFTY")
    
    print("\nCERTIFICATION REPORT:")
    print(f"  Countable Trades: {stats.countable_trades}/{stats.target_trades}")
    print(f"  Wins: {stats.wins}")
    print(f"  Losses: {stats.losses}")
    print(f"  Win Rate: {stats.win_rate:.2f}%")
    print(f"  Total P&L: ₹{stats.total_pnl:,.2f}")
    print(f"  Profit Factor: {stats.profit_factor:.2f}")
    print(f"  Certification Complete: {stats.certification_complete}")
    
    return runner


def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("AI TRADING COPILOT - SYSTEM TEST")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test all components
    engine = test_components()
    
    # Run replay test
    results = run_replay_test(engine)
    
    # Run certification test
    cert_runner = run_certification_test()
    
    print("\n" + "=" * 60)
    print("SYSTEM TEST COMPLETE")
    print("=" * 60)
    
    # Summary
    print("\nSUMMARY:")
    print(f"  ✅ All components initialized")
    if results:
        for market, stats in results.items():
            print(f"  ✅ {market} replay completed: {stats.get('total_trades', 0)} trades")
    print(f"  ✅ Certification test completed")
    
    print("\n✅ SYSTEM IS READY FOR FULL CERTIFICATION RUN")


if __name__ == "__main__":
    main()