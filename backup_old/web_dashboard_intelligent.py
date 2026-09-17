# web_dashboard_intelligent.py
# FIXED: Reads from the correct data source with premium values

import json
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Data directories
DATA_DIR = Path("data/dashboard")
PNL_DIR = Path("data/pnl")
PRE_MARKET_DIR = Path("data/reports/pre_market")
PAPER_TRADES_DIR = Path("data/paper_trades")
CONFIG_FILE = Path("config/deployment_config.json")

# LOT SIZES (SEBI 2026)
LOT_SIZES = {
    'NIFTY': 65,
    'SENSEX': 20,
    'BANKNIFTY': 25,
    'FINNIFTY': 40
}

def get_total_capital():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('deployed_capital', 1000000)
    except:
        pass
    return 1000000

def get_premium_from_position(pos):
    """Extract premium from position data."""
    # Check if premium is stored directly
    premium = pos.get('entry_premium', 0)
    if premium > 0:
        return premium
    
    # Check if entry_price is already premium (less than 10000)
    entry = pos.get('entry_price', 0)
    if entry < 10000:
        return entry
    
    # Otherwise, calculate from underlying
    symbol = pos.get('symbol', 'NIFTY')
    underlying = pos.get('underlying_price', entry)
    if symbol == 'NIFTY':
        return round(underlying * 0.008, 2)
    elif symbol == 'SENSEX':
        return round(underlying * 0.003, 2)
    return round(entry * 0.005, 2)

def calculate_position_pnl(pos):
    """Calculate P&L based on premium."""
    entry_premium = get_premium_from_position(pos)
    current_premium = pos.get('current_premium', entry_premium)
    quantity = pos.get('quantity', 0)
    
    pnl_amount = (current_premium - entry_premium) * quantity
    pnl_percent = ((current_premium / entry_premium) - 1) * 100 if entry_premium > 0 else 0
    
    return {
        'pnl_amount': pnl_amount,
        'pnl_percent': pnl_percent,
        'entry_premium': entry_premium,
        'current_premium': current_premium,
        'deployed': entry_premium * quantity
    }

@app.route('/')
def index():
    return render_template('dashboard_intelligent.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    try:
        response = {}
        
        # Read dashboard data
        files = list(DATA_DIR.glob("dashboard_*.json"))
        if not files:
            return jsonify({'error': 'No dashboard data found'})
        
        latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        with open(latest, 'r') as f:
            data = json.load(f)
        
        response['dashboard'] = data
        response['data_file'] = latest.name
        
        # Get total capital
        total_capital = get_total_capital()
        response['total_capital'] = total_capital
        
        # Process active positions with correct premium calculation
        positions = data.get('active_positions', [])
        active_positions = []
        total_deployed = 0
        total_pnl = 0
        winning = 0
        losing = 0
        
        for pos in positions:
            if pos.get('status') == 'OPEN':
                # Calculate using premium
                pnl = calculate_position_pnl(pos)
                
                # Get lot size
                symbol = pos.get('symbol', 'NIFTY')
                lot_size = LOT_SIZES.get(symbol, 65)
                lots = pos.get('lots', 0)
                quantity = lots * lot_size
                
                # Update position data with premium info
                pos['entry_premium'] = pnl['entry_premium']
                pos['current_premium'] = pnl['current_premium']
                pos['entry_price'] = pnl['entry_premium']  # Override with premium
                pos['current_price'] = pnl['current_premium']  # Override with premium
                pos['deployed_capital'] = pnl['deployed']
                pos['pnl_amount'] = pnl['pnl_amount']
                pos['pnl_percent'] = pnl['pnl_percent']
                pos['lot_size'] = lot_size
                pos['quantity'] = quantity
                
                active_positions.append(pos)
                total_deployed += pnl['deployed']
                total_pnl += pnl['pnl_amount']
                
                if pnl['pnl_amount'] > 0:
                    winning += 1
                elif pnl['pnl_amount'] < 0:
                    losing += 1
        
        response['active_positions'] = active_positions
        response['capital_deployed'] = total_deployed
        response['usage_percent'] = (total_deployed / total_capital * 100) if total_capital > 0 else 0
        
        # P&L Summary
        total_trades = winning + losing
        response['pnl'] = {
            'net': total_pnl,
            'winning_trades': winning,
            'losing_trades': losing,
            'total_trades': total_trades,
            'win_rate': (winning / total_trades * 100) if total_trades > 0 else 0,
            'profit': max(total_pnl, 0),
            'loss': abs(min(total_pnl, 0))
        }
        
        # Pre-market data
        pre_files = list(PRE_MARKET_DIR.glob("pre_market_*.json"))
        if pre_files:
            latest_pre = sorted(pre_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            with open(latest_pre, 'r') as f:
                response['pre_market'] = json.load(f)
        
        response['system_status'] = {
            'timestamp': datetime.now().isoformat(),
            'file': latest.name,
            'positions': len(active_positions),
            'total_capital': total_capital,
            'deployed': total_deployed,
            'usage_percent': response['usage_percent']
        }
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()})

if __name__ == '__main__':
    Path("templates").mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🧠 AI TRADING DASHBOARD - FIXED")
    print("=" * 60)
    print("")
    print("📊 Dashboard URL: http://localhost:5000")
    print("")
    print("📊 FIXED: Now showing PREMIUM values (not underlying)")
    print("  ✅ Entry prices are PREMIUMS")
    print("  ✅ Deployed capital = Premium × Quantity")
    print("  ✅ P&L based on premium changes")
    print("")
    print("⚠️  Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
