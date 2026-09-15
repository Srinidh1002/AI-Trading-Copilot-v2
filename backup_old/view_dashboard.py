# view_dashboard.py
# Quick dashboard viewer - run this in a separate terminal

import json
import os
from pathlib import Path
from datetime import datetime
import glob

print("=" * 80)
print("📊 AI TRADING DASHBOARD - LIVE VIEW")
print("=" * 80)
print("")

# Find the latest dashboard file
dashboard_files = sorted(
    Path("data/dashboard").glob("dashboard_*.json"),
    key=lambda x: x.stat().st_mtime,
    reverse=True
)

if not dashboard_files:
    print("❌ No dashboard data found. System may not be running yet.")
    exit(1)

latest_file = dashboard_files[0]
print(f"📄 Reading: {latest_file.name}")
print(f"📅 Last Updated: {datetime.fromtimestamp(latest_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)
print("")

try:
    with open(latest_file, 'r') as f:
        data = json.load(f)
except:
    print("❌ Could not read dashboard file (may be locked).")
    exit(1)

# System Status
status = data.get('system_status', {})
print(f"🟢 SYSTEM STATUS: {status.get('status', 'UNKNOWN')}")
print(f"   Uptime: {status.get('uptime', 0)} seconds")
print(f"   Cycle: {status.get('cycle', 0)}")
print("")

# Market Data
print("📈 LIVE MARKET DATA:")
for symbol, market in data.get('market_data', {}).items():
    print(f"   {symbol}: {market.get('ltp', 0):.2f} ({market.get('change_percent', 0):+.2f}%)")
print("")

# Positions
positions = data.get('active_positions', [])
print(f"📊 ACTIVE POSITIONS: {len(positions)}")
for pos in positions:
    pnl = pos.get('pnl_percent', 0)
    print(f"   {pos.get('symbol')} #{pos.get('position_number', 1)}: {pos.get('option_type')} @ {pos.get('entry_price', 0):.2f} (P&L: {pnl:+.2f}%)")
print("")

# Signals
signals = data.get('trade_signals', [])
print(f"🎯 RECENT SIGNALS ({len(signals)}):")
for signal in signals[-5:]:
    print(f"   {signal.get('signal')}: {signal.get('market')} {signal.get('option_type')} - {signal.get('reason', '')}")
print("")

# Decisions
decisions = data.get('decisions', [])
print(f"📋 RECENT DECISIONS ({len(decisions)}):")
for decision in decisions[-5:]:
    print(f"   {decision.get('decision')}: {decision.get('market')} {decision.get('option_type')} @ {decision.get('entry_price', 0)}")
print("")

# P&L
pnl = data.get('pnl_data', {})
daily = pnl.get('daily', {})
weekly = pnl.get('weekly', {})
monthly = pnl.get('monthly', {})
print(f"💰 P&L:")
print(f"   Daily: ₹{daily.get('profit', 0) - daily.get('loss', 0):.2f} (Trades: {daily.get('trades', 0)}, Win Rate: {daily.get('win_rate', 0):.1f}%)")
print(f"   Weekly: ₹{weekly.get('profit', 0) - weekly.get('loss', 0):.2f} (Trades: {weekly.get('trades', 0)})")
print(f"   Monthly: ₹{monthly.get('profit', 0) - monthly.get('loss', 0):.2f} (Trades: {monthly.get('trades', 0)})")
print("")

# Certification
cert = data.get('certification', {})
nifty_score = cert.get('NIFTY', 0)
sensex_score = cert.get('SENSEX', 0)
print(f"📋 CERTIFICATION:")
print(f"   NIFTY: {nifty_score}/100")
print(f"   SENSEX: {sensex_score}/100")
print("")

print("=" * 80)
print("💡 Press Ctrl+C to stop, or run again to refresh")
