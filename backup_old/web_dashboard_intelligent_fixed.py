# web_dashboard_intelligent.py
# FIXED: Capital display - prevents deployed > total capital

import json
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify
import threading

app = Flask(__name__)

# Data directories
DATA_DIR = Path("data/dashboard")
PNL_DIR = Path("data/pnl")
PRE_MARKET_DIR = Path("data/reports/pre_market")
CONFIG_FILE = Path("config/deployment_config.json")

def get_total_capital():
    """Get total capital from config, default ₹1,000,000"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('deployed_capital', 1000000)
    except:
        pass
    return 1000000  # Default ₹10 Lakhs

def get_deployed_capital(data):
    """Calculate deployed capital from active positions ONLY"""
    total = 0
    for pos in data.get('active_positions', []):
        if pos.get('status') == 'OPEN':
            entry_price = pos.get('entry_price', 0)
            quantity = pos.get('quantity', 0)
            total += entry_price * quantity
    return total

@app.route('/')
def index():
    return render_template('dashboard_intelligent.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    """Full dashboard data with intelligence"""
    try:
        response = {}
        
        # 1. Dashboard data
        files = list(DATA_DIR.glob("dashboard_*.json"))
        if files:
            latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            with open(latest, 'r') as f:
                data = json.load(f)
                response['dashboard'] = data
                
                # Get total capital from config
                total_capital = get_total_capital()
                response['total_capital'] = total_capital
                
                # Calculate deployed capital from positions (NOT from paper_trades)
                deployed = get_deployed_capital(data)
                response['capital_deployed'] = deployed
                
                # Ensure deployed never exceeds total (safety clamp)
                if deployed > total_capital:
                    response['capital_deployed'] = total_capital
                    response['warning'] = 'Deployed capital exceeds total - positions may be misreported'
        
        # 2. P&L data
        pnl_files = list(PNL_DIR.glob("daily_*.json"))
        if pnl_files:
            latest_pnl = sorted(pnl_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            with open(latest_pnl, 'r') as f:
                pnl_data = json.load(f)
                response['pnl'] = pnl_data.get('metrics', {})
                response['trades'] = pnl_data.get('trades', [])
        
        # 3. Pre-market report
        pre_market_files = list(PRE_MARKET_DIR.glob("pre_market_*.json"))
        if pre_market_files:
            latest_pre = sorted(pre_market_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            with open(latest_pre, 'r') as f:
                response['pre_market'] = json.load(f)
        
        # 4. System status
        response['system_status'] = {
            'timestamp': datetime.now().isoformat(),
            'file': latest.name if files else None
        }
        
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/pre_market')
def get_pre_market():
    try:
        files = list(PRE_MARKET_DIR.glob("pre_market_*.json"))
        if files:
            latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            with open(latest, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({'error': 'No pre-market data'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/indicators')
def get_indicators():
    try:
        files = list(DATA_DIR.glob("dashboard_*.json"))
        if files:
            latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            with open(latest, 'r') as f:
                data = json.load(f)
                return jsonify(data.get('indicators', {}))
        return jsonify({'error': 'No indicators data'})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    Path("templates").mkdir(exist_ok=True)
    
    total = get_total_capital()
    print("=" * 60)
    print("🧠 AI TRADING DASHBOARD - INTELLIGENT")
    print("=" * 60)
    print("")
    print(f"💰 Total Capital: ₹{total:,.2f}")
    print("📊 Dashboard URL: http://localhost:5000")
    print("📡 API: /api/dashboard, /api/pre_market, /api/indicators")
    print("")
    print("⚠️  Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
