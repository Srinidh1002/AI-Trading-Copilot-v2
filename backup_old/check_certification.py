"""
Check Certification Status
"""
import json
from pathlib import Path
from datetime import datetime

def check_certification():
    cert_path = Path("data/certification")
    
    print("=" * 60)
    print("CERTIFICATION STATUS")
    print(f"Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    if not cert_path.exists():
        print("❌ No certification data found. Run paper trading first.")
        return
    
    for market in ["NIFTY", "SENSEX"]:
        stats_file = cert_path / f"{market}_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                stats = json.load(f)
            print(f"\n📊 {market}:")
            print(f"   Countable Trades: {stats.get('countable_trades', 0)}/{stats.get('target_trades', 100)}")
            print(f"   Wins: {stats.get('wins', 0)}")
            print(f"   Losses: {stats.get('losses', 0)}")
            print(f"   Win Rate: {stats.get('win_rate', 0):.1f}%")
            print(f"   Total P&L: ₹{stats.get('total_pnl', 0):,.2f}")
            print(f"   Profit Factor: {stats.get('profit_factor', 0):.2f}")
            print(f"   Max Drawdown: ₹{stats.get('max_drawdown', 0):,.2f}")
            
            if stats.get('certification_complete', False):
                print("   ✅ CERTIFICATION COMPLETE!")
            else:
                remaining = stats.get('target_trades', 100) - stats.get('countable_trades', 0)
                print(f"   ⏳ {remaining} trades remaining")
        else:
            print(f"\n📊 {market}: No certification data yet")
            print("   Run paper trading to start certification")

if __name__ == "__main__":
    check_certification()
