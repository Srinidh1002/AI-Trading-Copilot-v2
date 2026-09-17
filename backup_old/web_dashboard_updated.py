# web_dashboard_updated.py
# Updated Web Dashboard with P&L and Capital Info

import json
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify
import threading

app = Flask(__name__)

# Data directory
DATA_DIR = Path("data/dashboard")
PNL_DIR = Path("data/pnl")

@app.route('/')
def index():
    return render_template('dashboard_updated.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    """API endpoint for dashboard data"""
    try:
        # Get latest dashboard file
        files = list(DATA_DIR.glob("dashboard_*.json"))
        if not files:
            return jsonify({'error': 'No dashboard data found'})
        
        latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        
        with open(latest, 'r') as f:
            data = json.load(f)
        
        # Add P&L data from pnl tracker
        pnl_files = list(PNL_DIR.glob("daily_*.json"))
        if pnl_files:
            latest_pnl = sorted(pnl_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            with open(latest_pnl, 'r') as f:
                pnl_data = json.load(f)
                data['pnl_data'] = pnl_data.get('metrics', {})
                data['trades'] = pnl_data.get('trades', [])
        
        # Calculate capital deployed
        capital_deployed = 0
        for pos in data.get('active_positions', []):
            if pos.get('status') == 'OPEN':
                entry_price = pos.get('entry_price', 0)
                quantity = pos.get('quantity', 0)
                capital_deployed += entry_price * quantity
        
        data['capital_deployed'] = capital_deployed
        data['_file'] = latest.name
        data['_last_updated'] = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/status')
def get_status():
    try:
        files = list(DATA_DIR.glob("dashboard_*.json"))
        if files:
            latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            return jsonify({
                'status': 'running',
                'file': latest.name,
                'last_updated': datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
            })
        return jsonify({'status': 'no_data'})
    except:
        return jsonify({'status': 'error'})

if __name__ == '__main__':
    Path("templates").mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🌐 AI TRADING DASHBOARD - UPDATED")
    print("=" * 60)
    print("")
    print("📊 Dashboard URL: http://localhost:5000")
    print("📡 API URL: http://localhost:5000/api/dashboard")
    print("")
    print("📊 Features:")
    print("  ✅ Live Market Data")
    print("  ✅ Active Positions with Lot Sizes")
    print("  ✅ Capital Deployed")
    print("  ✅ P&L (Daily/Weekly/Monthly)")
    print("  ✅ Win/Loss Summary")
    print("  ✅ Recent Trades")
    print("")
    print("⚠️  Press Ctrl+C to stop the server")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
