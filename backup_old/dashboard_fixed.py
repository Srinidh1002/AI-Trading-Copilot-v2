# dashboard_fixed.py - FIXED DASHBOARD WITH WORKING ANGEL ONE API

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import sys
import os
import time
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="F&O Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .positive { color: #00ff00; font-weight: bold; }
    .negative { color: #ff4444; font-weight: bold; }
    .neutral { color: #ffaa00; font-weight: bold; }
    .card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        margin: 5px;
        border: 1px solid #333;
    }
    .metric-value { font-size: 22px; font-weight: bold; }
    .metric-label { font-size: 12px; color: #888888; }
    .status-connected { color: #00ff00; }
    .status-disconnected { color: #ff4444; }
    </style>
""", unsafe_allow_html=True)


def get_real_data():
    """Get REAL data from Angel One API using the fixed version."""
    try:
        from services.market.angel_one_api_fixed import AngelOneAPIFixed
        
        api = AngelOneAPIFixed()
        
        if api.authenticate():
            data = {
                'nifty_ltp': api.get_ltp('NIFTY'),
                'sensex_ltp': api.get_ltp('SENSEX'),
                'nifty_chain': api.get_option_chain('NIFTY'),
                'sensex_chain': api.get_option_chain('SENSEX'),
                'timestamp': datetime.now().isoformat(),
                'authenticated': True,
                'using_fallback': False
            }
            
            # Get ATM data
            for symbol in ['NIFTY', 'SENSEX']:
                chain = data[f'{symbol.lower()}_chain']
                if chain:
                    strikes = chain.get('strikes', [])
                    if strikes:
                        underlying = chain.get('underlying', 0)
                        atm = min(strikes, key=lambda s: abs(s['strike'] - underlying))
                        data[f'{symbol.lower()}_atm'] = {
                            'strike': atm['strike'],
                            'call_ltp': atm.get('call_ltp', 0),
                            'put_ltp': atm.get('put_ltp', 0),
                            'pcr': atm.get('pcr', 0)
                        }
            
            return data
    except Exception as e:
        return {'error': str(e), 'authenticated': False}
    
    return None


def get_fallback_data():
    """Get data from WebSocket bridge if Angel One fails."""
    try:
        from services.market.websocket_bridge import WebSocketBridge
        bridge = WebSocketBridge('data/task9/live_stream')
        bridge.initialize()
        market_data = bridge.get_latest_data()
        
        return {
            'nifty_ltp': market_data.get('NIFTY', {}).get('ltp', 0),
            'sensex_ltp': market_data.get('SENSEX', {}).get('ltp', 0),
            'authenticated': False,
            'using_fallback': True,
            'timestamp': datetime.now().isoformat()
        }
    except:
        return None


def create_option_chain_table(chain_data):
    """Create option chain table."""
    if not chain_data:
        return pd.DataFrame()
    
    strikes = chain_data.get('strikes', [])
    if not strikes:
        return pd.DataFrame()
    
    df = pd.DataFrame(strikes)
    
    # Select and format columns
    columns = ['strike', 'call_ltp', 'call_oi', 'call_oi_change', 'put_ltp', 'put_oi', 'put_oi_change', 'pcr']
    df = df[[c for c in columns if c in df.columns]]
    
    df.columns = ['Strike', 'CALL LTP', 'CALL OI', 'CALL OI%', 'PUT LTP', 'PUT OI', 'PUT OI%', 'PCR']
    
    for col in ['CALL LTP', 'PUT LTP']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"₹{x:.2f}" if x > 0 else "-")
    
    for col in ['CALL OI', 'PUT OI']:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:,.0f}" if x > 0 else "-")
    
    return df


def main():
    st.title("📈 F&O Trading Dashboard - Live")
    
    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S IST')
    st.caption(f"Live Data from Angel One | {current_time}")
    
    # Refresh button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Get data
    data = get_real_data()
    
    # If Angel One fails, try fallback
    if not data or not data.get('authenticated'):
        st.warning("⚠️ Angel One API not responding, trying fallback data...")
        data = get_fallback_data()
    
    if data and data.get('authenticated'):
        # ===== STATUS =====
        status_text = "✅ Connected to Angel One"
        status_color = "status-connected"
        if data.get('using_fallback'):
            status_text = "🔄 Using Fallback Data"
            status_color = "neutral"
        
        st.markdown(f'<div class="{status_color}">{status_text}</div>', unsafe_allow_html=True)
        
        # ===== TOP METRICS =====
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            nifty = data.get('nifty_ltp', 0)
            st.metric("NIFTY", f"₹{nifty:,.2f}")
        
        with col2:
            sensex = data.get('sensex_ltp', 0)
            st.metric("SENSEX", f"₹{sensex:,.2f}")
        
        with col3:
            nifty_atm = data.get('nifty_atm', {})
            st.metric("NIFTY ATM CALL", f"₹{nifty_atm.get('call_ltp', 0):.2f}")
        
        with col4:
            sensex_atm = data.get('sensex_atm', {})
            st.metric("SENSEX ATM CALL", f"₹{sensex_atm.get('call_ltp', 0):.2f}")
        
        with col5:
            nifty_chain = data.get('nifty_chain', {})
            pcr = nifty_chain.get('total_pcr', 0)
            color = "🟢" if pcr < 0.5 else "🟡" if pcr < 1.0 else "🔴"
            st.metric("NIFTY PCR", f"{color} {pcr:.2f}")
        
        # ===== OPTION CHAINS =====
        tab1, tab2 = st.tabs(["NIFTY Option Chain", "SENSEX Option Chain"])
        
        with tab1:
            chain = data.get('nifty_chain', {})
            df = create_option_chain_table(chain)
            if not df.empty:
                st.dataframe(df, use_container_width=True, height=400)
                
                # Chart
                strikes = chain.get('strikes', [])
                if strikes:
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=[s['strike'] for s in strikes],
                        y=[s.get('call_ltp', 0) for s in strikes],
                        mode='lines+markers',
                        name='CALL Premium',
                        line=dict(color='green', width=2),
                        marker=dict(size=8)
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=[s['strike'] for s in strikes],
                        y=[s.get('put_ltp', 0) for s in strikes],
                        mode='lines+markers',
                        name='PUT Premium',
                        line=dict(color='red', width=2),
                        marker=dict(size=8)
                    ))
                    
                    fig.update_layout(
                        title="Option Premiums by Strike",
                        xaxis_title="Strike Price",
                        yaxis_title="Premium (₹)",
                        height=400,
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No option chain data available")
        
        with tab2:
            chain = data.get('sensex_chain', {})
            df = create_option_chain_table(chain)
            if not df.empty:
                st.dataframe(df, use_container_width=True, height=400)
            else:
                st.info("No option chain data available")
        
        # ===== RECOMMENDATIONS =====
        st.subheader("📊 Trading Recommendations")
        
        col1, col2 = st.columns(2)
        
        # NIFTY
        with col1:
            nifty_chain = data.get('nifty_chain', {})
            pcr = nifty_chain.get('total_pcr', 0.5)
            nifty_atm = data.get('nifty_atm', {})
            
            if pcr < 0.5:
                action = "BUY CALL"
                color = "#00ff00"
                emoji = "🟢"
            elif pcr > 1.0:
                action = "BUY PUT"
                color = "#ff4444"
                emoji = "🔴"
            else:
                action = "WAIT"
                color = "#ffaa00"
                emoji = "🟡"
            
            st.markdown(f"""
            <div class="card">
                <div style="font-size: 18px; font-weight: bold;">NIFTY</div>
                <div style="font-size: 24px; color: {color};">
                    {emoji} {action}
                </div>
                <div style="margin-top: 10px;">
                    <div><span style="color:#888;">ATM Strike:</span> {nifty_atm.get('strike', 0)}</div>
                    <div><span style="color:#888;">CALL Premium:</span> ₹{nifty_atm.get('call_ltp', 0):.2f}</div>
                    <div><span style="color:#888;">PUT Premium:</span> ₹{nifty_atm.get('put_ltp', 0):.2f}</div>
                    <div><span style="color:#888;">PCR:</span> {pcr:.2f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # SENSEX
        with col2:
            sensex_chain = data.get('sensex_chain', {})
            pcr = sensex_chain.get('total_pcr', 0.5)
            sensex_atm = data.get('sensex_atm', {})
            
            if pcr < 0.5:
                action = "BUY CALL"
                color = "#00ff00"
                emoji = "🟢"
            elif pcr > 1.0:
                action = "BUY PUT"
                color = "#ff4444"
                emoji = "🔴"
            else:
                action = "WAIT"
                color = "#ffaa00"
                emoji = "🟡"
            
            st.markdown(f"""
            <div class="card">
                <div style="font-size: 18px; font-weight: bold;">SENSEX</div>
                <div style="font-size: 24px; color: {color};">
                    {emoji} {action}
                </div>
                <div style="margin-top: 10px;">
                    <div><span style="color:#888;">ATM Strike:</span> {sensex_atm.get('strike', 0)}</div>
                    <div><span style="color:#888;">CALL Premium:</span> ₹{sensex_atm.get('call_ltp', 0):.2f}</div>
                    <div><span style="color:#888;">PUT Premium:</span> ₹{sensex_atm.get('put_ltp', 0):.2f}</div>
                    <div><span style="color:#888;">PCR:</span> {pcr:.2f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    elif data and data.get('using_fallback'):
        # Fallback data display
        st.info("📊 Using Fallback Data (WebSocket Bridge)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("NIFTY", f"₹{data.get('nifty_ltp', 0):,.2f}")
        with col2:
            st.metric("SENSEX", f"₹{data.get('sensex_ltp', 0):,.2f}")
        
        st.warning("⚠️ Option chain data not available in fallback mode")
    
    else:
        st.error("❌ Error: No data available")
        st.info("Please check your .env file has the correct Angel One credentials:")
        st.code("""
        ANGEL_API_KEY=your_api_key
        ANGEL_CLIENT_ID=your_client_id
        ANGEL_PIN=your_pin
        ANGEL_TOTP_SECRET=your_totp_secret
        """)
    
    # ===== SIDEBAR =====
    st.sidebar.title("⚙️ Controls")
    
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
    refresh_rate = st.sidebar.selectbox("Refresh Rate (seconds)", [3, 5, 10, 15, 30], index=1)
    
    if auto_refresh:
        st.sidebar.info(f"🔄 Auto refreshing every {refresh_rate} seconds")
        time.sleep(refresh_rate)
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Connection status
    with st.sidebar.expander("🔐 Connection Status"):
        if data and data.get('authenticated'):
            st.success("✅ Connected to Angel One")
            if data.get('using_fallback'):
                st.warning("🔄 Using simulated data")
        elif data and data.get('using_fallback'):
            st.warning("🔄 Using fallback data")
        else:
            st.error("❌ Not connected")
    
    st.sidebar.caption("🚀 F&O Trading Dashboard v2.0")
    st.sidebar.caption("Powered by Angel One API")


if __name__ == "__main__":
    main()
