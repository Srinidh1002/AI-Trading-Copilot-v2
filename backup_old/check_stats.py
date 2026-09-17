"""
Check Paper Trading Stats
"""
import json
from pathlib import Path
from datetime import datetime

def show_stats():
    trades_path = Path("data/paper_trades")
    
    print("=" * 60)
    print("PAPER TRADING STATUS")
    print(f"Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    if not trades_path.exists():
        print("❌ No stats found - Paper trading may not be running")
        return
    
    for market in ["NIFTY", "SENSEX"]:
        stats_file = trades_path / f"{market}_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                stats = json.load(f)
            print(f"\n📊 {market}:")
            print(f"   Total Trades: {stats.get('total_trades', 0)}")
            print(f"   Wins: {stats.get('wins', 0)}")
            print(f"   Losses: {stats.get('losses', 0)}")
            print(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
            print(f"   Total P&L: ₹{stats.get('total_pnl', 0):,.2f}")
        else:
            print(f"\n📊 {market}: No stats yet")
    
    # Check active trades via engine
    try:
        from services.trading.paper_engine import PaperTradingEngine
        engine = PaperTradingEngine({"mode": "paper"})
        active = engine.get_active_trades()
        if active:
            print("\n📈 ACTIVE TRADES:")
            for trade in active:
                print(f"   {trade.market} {trade.direction} @ {trade.entry_price:.2f} | Status: {trade.status}")
        else:
            print("\n📈 No active trades in engine")
            
        closed = engine.get_closed_trades()
        if closed:
            print(f"\n📋 Closed Trades: {len(closed)}")
            for trade in closed[-3:]:
                emoji = "✅" if trade.pnl > 0 else "❌"
                print(f"   {emoji} {trade.market} {trade.direction} | P&L: ₹{trade.pnl:.2f} | {trade.exit_reason}")
    except Exception as e:
        print(f"\n⚠️ Could not connect to engine: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    show_stats()
