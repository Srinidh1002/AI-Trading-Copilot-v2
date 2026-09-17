# web_dashboard_intelligent.py
# ADDED: Capital display

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
                
                # Calculate capital deployed from positions
                capital_deployed = 0
                for pos in data.get('active_positions', []):
                    if pos.get('status') == 'OPEN':
                        entry_price = pos.get('entry_price', 0)
                        quantity = pos.get('quantity', 0)
                        capital_deployed += entry_price * quantity
                response['capital_deployed'] = capital_deployed
                
                # Get total capital from config
                try:
                    with open('config/deployment_config.json', 'r') as f:
                        config = json.load(f)
                        response['total_capital'] = config.get('deployed_capital', 1000000)
                except:
                    response['total_capital'] = 1000000
        
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
    
    print("=" * 60)
    print("🧠 AI TRADING DASHBOARD - INTELLIGENT")
    print("=" * 60)
    print("")
    print("📊 Dashboard URL: http://localhost:5000")
    print("📡 API: /api/dashboard, /api/pre_market, /api/indicators")
    print("")
    print("📊 Features:")
    print("  ✅ Pre-market Analysis")
    print("  ✅ Technical Indicators")
    print("  ✅ Decisions & Signals")
    print("  ✅ Active Positions with Intelligence")
    print("  ✅ Capital Deployed & Total Capital")
    print("  ✅ P&L Summary")
    print("")
    print("⚠️  Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
