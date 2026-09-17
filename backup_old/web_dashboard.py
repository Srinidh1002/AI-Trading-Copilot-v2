# web_dashboard.py
# Flask Web Dashboard for AI Trading Copilot

import json
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, send_from_directory
import threading
import time

app = Flask(__name__)

# Data directory
DATA_DIR = Path("data/dashboard")

@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return render_template('dashboard.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    """API endpoint for dashboard data"""
    try:
        # Find latest dashboard file
        files = list(DATA_DIR.glob("dashboard_*.json"))
        if not files:
            return jsonify({'error': 'No dashboard data found'})
        
        latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
        
        with open(latest, 'r') as f:
            data = json.load(f)
        
        # Add file info
        data['_file'] = latest.name
        data['_last_updated'] = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/status')
def get_status():
    """Simple status endpoint"""
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
    # Create templates folder
    Path("templates").mkdir(exist_ok=True)
    
    print("=" * 60)
    print("🌐 AI TRADING DASHBOARD - WEB INTERFACE")
    print("=" * 60)
    print("")
    print("📊 Dashboard URL: http://localhost:5000")
    print("📡 API URL: http://localhost:5000/api/dashboard")
    print("")
    print("⚠️  Press Ctrl+C to stop the server")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
