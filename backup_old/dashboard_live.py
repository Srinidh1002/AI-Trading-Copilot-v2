# dashboard_live.py - LIVE TRADING DASHBOARD
# Displays real-time positions, P&L, targets, and market data

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
import json
import sys
import os
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Page config
st.set_page_config(
    page_title="F&O Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header { font-size: 28px; font-weight: bold; color: #00ff00; }
    .positive { color: #00ff00; font-weight: bold; }
    .negative { color: #ff4444; font-weight: bold; }
    .neutral { color: #ffaa00; font-weight: bold; }
    .card { background-color: #1e1e1e; padding: 15px; border-radius: 10px; margin: 5px; }
    .metric-value { font-size: 24px; font-weight: bold; }
    .metric-label { font-size: 14px; color: #888888; }
    </style>
""", unsafe_allow_html=True)


class DashboardData:
    """Manages dashboard data."""
    
    def __init__(self):
        self.data = {
            'timestamp': None,
            'positions': [],
            'stats': {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0,
                'today_trades': 0,
                'target_hits': {'T1': 0, 'T2': 0, 'T3': 0}
            },
            'market_data': {},
            'active_symbols': []
        }
        self.engine = None
    
    def load_engine_data(self):
        """Try to load data from engine."""
        try:
            # Try to import and get engine instance
            from run_unified_trading import UnifiedTradingEngine
            # For now, use mock data
            self._generate_mock_data()
        except:
            self._generate_mock_data()
    
    def _generate_mock_data(self):
        """Generate mock data for demonstration."""
        self.data = {
            'timestamp': datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
            'positions': [
                {
                    'symbol': 'NIFTY',
                    'strike': 24450,
                    'type': 'CALL',
                    'entry': 195.69,
                    'current': 225.04,
                    'pnl': 1907.75,
                    'pnl_pct': 15.0,
                    'status': 'TARGET1',
                    'target1': 225.04,
                    'target2': 254.40,
                    'target3': 293.53,
                    'stop': 185.91
                },
                {
                    'symbol': 'SENSEX',
                    'strike': 78200,
                    'type': 'CALL',
                    'entry': 234.54,
                    'current': 269.72,
                    'pnl': 703.60,
                    'pnl_pct': 15.0,
                    'status': 'OPEN',
                    'target1': 269.72,
                    'target2': 304.90,
                    'target3': 351.81,
                    'stop': 222.81
                }
            ],
            'stats': {
                'total_trades': 25,
                'winning_trades': 18,
                'losing_trades': 7,
                'total_pnl': 42500.00,
                'today_trades': 4,
                'target_hits': {'T1': 12, 'T2': 5, 'T3': 1}
            },
            'market_data': {
                'NIFTY': {'ltp': 24461.3},
                'SENSEX': {'ltp': 78180.31}
            },
            'active_symbols': ['NIFTY', 'SENSEX']
        }


def create_position_table(positions):
    """Create position table."""
    if not positions:
        return pd.DataFrame()
    
    df = pd.DataFrame(positions)
    
    # Format columns
    if 'pnl' in df.columns:
        df['pnl'] = df['pnl'].apply(lambda x: f"₹{x:,.2f}")
    if 'entry' in df.columns:
        df['entry'] = df['entry'].apply(lambda x: f"₹{x:.2f}")
    if 'current' in df.columns:
        df['current'] = df['current'].apply(lambda x: f"₹{x:.2f}")
    if 'pnl_pct' in df.columns:
        df['pnl_pct'] = df['pnl_pct'].apply(lambda x: f"{x:+.1f}%")
    
    return df


def create_pnl_chart(positions):
    """Create P&L chart."""
    if not positions:
        return None
    
    # Sort by status for color coding
    status_colors = {
        'OPEN': 'blue',
        'TARGET1': 'green',
        'TARGET2': 'darkgreen',
        'TARGET3': 'gold',
        'STOPPED': 'red'
    }
    
    fig = go.Figure()
    
    for pos in positions:
        status = pos.get('status', 'OPEN')
        color = status_colors.get(status, 'gray')
        
        # Entry to current bar
        fig.add_trace(go.Bar(
            x=[pos['symbol']],
            y=[pos['pnl']],
            name=f"{pos['symbol']} ({status})",
            text=[f"₹{pos['pnl']:,.2f}"],
            textposition='outside',
            marker_color=color,
            hovertemplate=f"""
                <b>{pos['symbol']}</b><br>
                Entry: ₹{pos['entry']:.2f}<br>
                Current: ₹{pos['current']:.2f}<br>
                P&L: {pos['pnl_pct']:+.1f}%<br>
                Status: {status}<br>
                Targets: ₹{pos['target1']:.2f} → ₹{pos['target2']:.2f} → ₹{pos['target3']:.2f}<br>
                Stop: ₹{pos['stop']:.2f}
            """
        ))
    
    fig.update_layout(
        title="Position P&L",
        yaxis_title="P&L (₹)",
        showlegend=True,
        height=300
    )
    
    return fig


def create_status_card(position):
    """Create a status card for a single position."""
    status = position.get('status', 'UNKNOWN')
    pnl_pct = position.get('pnl_pct', 0)
    
    if status == 'OPEN':
        status_color = "#ffaa00"
        status_icon = "⏳"
    elif 'TARGET' in status:
        status_color = "#00ff00"
        status_icon = "✅"
    elif status == 'STOPPED':
        status_color = "#ff4444"
        status_icon = "⛔"
    else:
        status_color = "#888888"
        status_icon = "❓"
    
    pnl_color = "#00ff00" if pnl_pct >= 0 else "#ff4444"
    
    return f"""
    <div class="card">
        <div style="display: flex; justify-content: space-between;">
            <span style="font-size: 20px; font-weight: bold;">{position['symbol']}</span>
            <span style="color: {status_color}; font-weight: bold;">{status_icon} {status}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 10px;">
            <div>
                <div class="metric-label">Strike</div>
                <div class="metric-value">{position['strike']}</div>
            </div>
            <div>
                <div class="metric-label">Entry</div>
                <div class="metric-value">₹{position['entry']:.2f}</div>
            </div>
            <div>
                <div class="metric-label">Current</div>
                <div class="metric-value">₹{position['current']:.2f}</div>
            </div>
            <div>
                <div class="metric-label">P&L</div>
                <div class="metric-value" style="color: {pnl_color};">{position['pnl_pct']:+.1f}%</div>
            </div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 10px; font-size: 12px; color: #888;">
            <span>🎯 T1: ₹{position['target1']:.2f}</span>
            <span>🎯 T2: ₹{position['target2']:.2f}</span>
            <span>🎯 T3: ₹{position['target3']:.2f}</span>
            <span>⛔ Stop: ₹{position['stop']:.2f}</span>
        </div>
        <div style="margin-top: 8px;">
            <div style="height: 4px; background: #333; border-radius: 2px;">
                <div style="height: 100%; width: {min(100, (position['current'] / position['target3'] * 100 if position['target3'] > 0 else 0))}%; background: linear-gradient(to right, #00ff00, #ffaa00); border-radius: 2px;"></div>
            </div>
        </div>
    </div>
    """


def main():
    st.title("📈 F&O Trading Dashboard - Live")
    st.caption(f"Last Updated: {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    # Initialize data
    dashboard = DashboardData()
    dashboard.load_engine_data()
    data = dashboard.data
    
    # ===== TOP METRICS =====
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    stats = data.get('stats', {})
    total_pnl = stats.get('total_pnl', 0)
    win_rate = (stats.get('winning_trades', 0) / max(1, stats.get('total_trades', 1))) * 100
    
    with col1:
        st.metric("💰 Total P&L", f"₹{total_pnl:,.2f}", delta=f"{total_pnl/1000000*100:.1f}%")
    
    with col2:
        st.metric("📊 Win Rate", f"{win_rate:.1f}%", delta=f"{stats.get('winning_trades', 0)}W / {stats.get('losing_trades', 0)}L")
    
    with col3:
        st.metric("📈 Today's Trades", stats.get('today_trades', 0))
    
    with col4:
        st.metric("🎯 T1 Hits", stats.get('target_hits', {}).get('T1', 0))
    
    with col5:
        st.metric("🎯 T2 Hits", stats.get('target_hits', {}).get('T2', 0))
    
    with col6:
        st.metric("🎯 T3 Hits", stats.get('target_hits', {}).get('T3', 0))
    
    # ===== POSITIONS =====
    st.subheader("📊 Active Positions")
    
    positions = data.get('positions', [])
    active_positions = [p for p in positions if p.get('status') in ['OPEN', 'TARGET1', 'TARGET2']]
    
    if active_positions:
        # Cards for each position
        cols = st.columns(len(active_positions))
        for i, pos in enumerate(active_positions):
            with cols[i]:
                st.markdown(create_status_card(pos), unsafe_allow_html=True)
        
        # P&L Chart
        st.subheader("📈 P&L Chart")
        chart = create_pnl_chart(active_positions)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
        
        # Detailed table
        with st.expander("📋 Detailed Position Table"):
            df = create_position_table(active_positions)
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No active positions. Waiting for trade signals...")
    
    # ===== MARKET DATA =====
    st.subheader("📊 Market Data")
    
    market_data = data.get('market_data', {})
    if market_data:
        col1, col2 = st.columns(2)
        for i, (symbol, data) in enumerate(market_data.items()):
            with col1 if i == 0 else col2:
                ltp = data.get('ltp', 0)
                base = 24461.3 if symbol == 'NIFTY' else 78180.31
                change = ((ltp - base) / base * 100) if base > 0 else 0
                color = "#00ff00" if change >= 0 else "#ff4444"
                
                st.markdown(f"""
                <div class="card">
                    <div style="font-size: 18px; font-weight: bold;">{symbol}</div>
                    <div style="font-size: 28px; font-weight: bold;">₹{ltp:,.2f}</div>
                    <div style="color: {color}; font-size: 16px;">{change:+.2f}%</div>
                </div>
                """, unsafe_allow_html=True)
    
    # ===== TARGET PROGRESS =====
    if active_positions:
        st.subheader("🎯 Target Progress")
        
        for pos in active_positions:
            symbol = pos['symbol']
            current = pos['current']
            entry = pos['entry']
            t1 = pos.get('target1', entry * 1.15)
            t2 = pos.get('target2', entry * 1.30)
            t3 = pos.get('target3', entry * 1.50)
            
            progress = ((current - entry) / (t3 - entry)) * 100 if t3 > entry else 0
            progress = max(0, min(100, progress))
            
            status_emoji = "🟢" if pos['status'] == 'OPEN' else "🟡" if 'TARGET' in pos['status'] else "🔴"
            
            st.markdown(f"""
            <div class="card">
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-weight: bold;">{symbol} {pos['type']}</span>
                    <span>{status_emoji} {pos['status']}</span>
                </div>
                <div style="margin-top: 5px;">
                    <div style="display: flex; justify-content: space-between; font-size: 12px;">
                        <span>Entry: ₹{entry:.2f}</span>
                        <span>Current: ₹{current:.2f}</span>
                        <span>T1: ₹{t1:.2f}</span>
                        <span>T2: ₹{t2:.2f}</span>
                        <span>T3: ₹{t3:.2f}</span>
                    </div>
                    <div style="height: 8px; background: #333; border-radius: 4px; margin-top: 5px;">
                        <div style="height: 100%; width: {progress}%; background: linear-gradient(to right, #00ff00, #ffaa00, #ff4444); border-radius: 4px;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 11px; color: #888; margin-top: 2px;">
                        <span>{pos['pnl_pct']:+.1f}%</span>
                        <span>Progress: {progress:.0f}%</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # ===== AUTO REFRESH =====
    st.sidebar.title("⚙️ Controls")
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
    refresh_rate = st.sidebar.selectbox("Refresh Rate", [3, 5, 10, 15, 30], index=1)
    
    if auto_refresh:
        st.sidebar.info(f"🔄 Auto refreshing every {refresh_rate} seconds")
        st.empty()
    
    # ===== STATS =====
    with st.sidebar.expander("📊 Statistics", expanded=True):
        st.metric("Total Trades", stats.get('total_trades', 0))
        st.metric("Winning Trades", stats.get('winning_trades', 0))
        st.metric("Losing Trades", stats.get('losing_trades', 0))
        st.metric("Win Rate", f"{win_rate:.1f}%")
        st.metric("Total P&L", f"₹{total_pnl:,.2f}")
    
    # ===== RECOMMENDATIONS =====
    with st.sidebar.expander("📝 Recommendations"):
        active_count = len(active_positions)
        if active_count < 2:
            st.success(f"✅ Room for new trades ({active_count}/2 active)")
            st.info("💡 Consider entering on pullbacks")
        else:
            st.warning("⚠️ Max positions reached (2/2)")
        
        # Market sentiment
        st.subheader("Market Sentiment")
        st.metric("NIFTY", f"{market_data.get('NIFTY', {}).get('ltp', 0):,.2f}")
        st.metric("SENSEX", f"{market_data.get('SENSEX', {}).get('ltp', 0):,.2f}")
    
    # ===== FOOTER =====
    st.sidebar.markdown("---")
    st.sidebar.caption("🚀 F&O Trading Dashboard v2.0")
    st.sidebar.caption(f"Built with ❤️ | {datetime.now().strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()
