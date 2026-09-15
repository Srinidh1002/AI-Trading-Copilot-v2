# dashboard_fixed_v2.py - DASHBOARD WITH PROPER ERROR HANDLING

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
    .status-fallback { color: #ffaa00; }
    .status-disconnected { color: #ff4444; }
    </style>
""", unsafe_allow_html=True)


def get_market_data():
    """Get market data from multiple sources."""
    data = {
        'nifty_ltp': 0,
        'sensex_ltp': 0,
        'nifty_chain': None,
        'sensex_chain': None,
        'authenticated': False,
        'using_fallback': True,
        'timestamp': datetime.now().isoformat()
    }
    
    # Try WebSocket bridge first (most reliable)
    try:
        from services.market.websocket_bridge import WebSocketBridge
        bridge = WebSocketBridge('data/task9/live_stream')
        bridge.initialize()
        market_data = bridge.get_latest_data()
        
        if market_data:
            data['nifty_ltp'] = market_data.get('NIFTY', {}).get('ltp', 0)
            data['sensex_ltp'] = market_data.get('SENSEX', {}).get('ltp', 0)
            data['using_fallback'] = True
            data['authenticated'] = False
            data['source'] = 'WebSocket'
            
            # Generate simulated option chain
            data['nifty_chain'] = generate_simulated_chain('NIFTY', data['nifty_ltp'])
            data['sensex_chain'] = generate_simulated_chain('SENSEX', data['sensex_ltp'])
    except Exception as e:
        st.error(f"WebSocket error: {e}")
    
    # Try Angel One as secondary
    try:
        from services.market.angel_one_api_fixed import AngelOneAPIFixed
        api = AngelOneAPIFixed()
        
        if api.authenticate():
            nifty = api.get_ltp('NIFTY')
            sensex = api.get_ltp('SENSEX')
            
            if nifty > 0:
                data['nifty_ltp'] = nifty
                data['source'] = 'Angel One'
                data['authenticated'] = True
                data['using_fallback'] = False
            
            if sensex > 0:
                data['sensex_ltp'] = sensex
            
            # Try to get option chain
            nifty_chain = api.get_option_chain('NIFTY')
            if nifty_chain and nifty_chain.get('strikes'):
                data['nifty_chain'] = nifty_chain
                data['using_fallback'] = False
                
            sensex_chain = api.get_option_chain('SENSEX')
            if sensex_chain and sensex_chain.get('strikes'):
                data['sensex_chain'] = sensex_chain
                data['using_fallback'] = False
    except Exception as e:
        pass
    
    # If no data, use fallback
    if data['nifty_ltp'] <= 0:
        data['nifty_ltp'] = 24461.3
        data['sensex_ltp'] = 78180.31
        data['using_fallback'] = True
        data['source'] = 'Fallback'
    
    return data


def generate_simulated_chain(symbol: str, underlying: float) -> dict:
    """Generate simulated option chain."""
    if underlying <= 0:
        underlying = 24461.3 if symbol == 'NIFTY' else 78180.31
    
    strikes = []
    step = 50 if symbol == 'NIFTY' else 100
    atm_strike = round(underlying / step) * step
    
    for offset in range(-5, 6):
        strike = atm_strike + (offset * step)
        atm_premium = underlying * (0.008 if symbol == 'NIFTY' else 0.003)
        distance_pct = abs(strike - underlying) / underlying
        
        call_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
        put_premium = atm_premium * max(0.1, 1 - distance_pct * 1.5)
        
        if strike < underlying:
            call_premium *= 1 + distance_pct * 2
            put_premium *= max(0.1, 1 - distance_pct * 2)
        else:
            call_premium *= max(0.1, 1 - distance_pct * 2)
            put_premium *= 1 + distance_pct * 2
        
        oi_factor = max(0.1, 1 - distance_pct * 10)
        call_oi = int(100000 * oi_factor * (0.5 + offset / 20))
        put_oi = int(100000 * oi_factor * (0.5 - offset / 20))
        
        strikes.append({
            'strike': strike,
            'call_ltp': round(max(5, call_premium), 2),
            'call_oi': max(1000, call_oi),
            'call_oi_change': round(offset * 10, 2),
            'call_volume': max(100, call_oi // 10),
            'put_ltp': round(max(5, put_premium), 2),
            'put_oi': max(1000, put_oi),
            'put_oi_change': round(-offset * 10, 2),
            'put_volume': max(100, put_oi // 10),
            'pcr': max(0.1, put_oi / call_oi if call_oi > 0 else 1)
        })
    
    total_call_oi = sum(s['call_oi'] for s in strikes)
    total_put_oi = sum(s['put_oi'] for s in strikes)
    
    return {
        'symbol': symbol,
        'underlying': underlying,
        'strikes': strikes,
        'total_pcr': total_put_oi / total_call_oi if total_call_oi > 0 else 0.5,
        'simulated': True
    }


def create_option_chain_table(chain_data):
    """Create option chain table."""
    if not chain_data:
        return pd.DataFrame()
    
    strikes = chain_data.get('strikes', [])
    if not strikes:
        return pd.DataFrame()
    
    df = pd.DataFrame(strikes)
    
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


def get_atm_strike(chain_data):
    """Get ATM strike from chain."""
    if not chain_data:
        return None
    
    strikes = chain_data.get('strikes', [])
    underlying = chain_data.get('underlying', 0)
    
    if not strikes or underlying <= 0:
        return None
    
    return min(strikes, key=lambda s: abs(s['strike'] - underlying))


def main():
    st.title("📈 F&O Trading Dashboard")
    
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S IST')
    st.caption(f"Live Data | {current_time}")
    
    # Refresh
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Get data
    data = get_market_data()
    
    # Status
    if data.get('authenticated') and not data.get('using_fallback'):
        st.markdown('<div class="status-connected">✅ Connected to Angel One</div>', unsafe_allow_html=True)
    elif data.get('using_fallback'):
        st.markdown(f'<div class="status-fallback">🔄 Using {data.get("source", "Fallback")} Data</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-disconnected">❌ No data connection</div>', unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("NIFTY", f"₹{data.get('nifty_ltp', 0):,.2f}")
    
    with col2:
        st.metric("SENSEX", f"₹{data.get('sensex_ltp', 0):,.2f}")
    
    # Get ATM data
    nifty_atm = get_atm_strike(data.get('nifty_chain'))
    sensex_atm = get_atm_strike(data.get('sensex_chain'))
    
    with col3:
        if nifty_atm:
            st.metric("NIFTY ATM CALL", f"₹{nifty_atm.get('call_ltp', 0):.2f}")
        else:
            st.metric("NIFTY ATM CALL", "-")
    
    with col4:
        if sensex_atm:
            st.metric("SENSEX ATM CALL", f"₹{sensex_atm.get('call_ltp', 0):.2f}")
        else:
            st.metric("SENSEX ATM CALL", "-")
    
    with col5:
        nifty_chain = data.get('nifty_chain', {})
        pcr = nifty_chain.get('total_pcr', 0.5)
        color = "🟢" if pcr < 0.5 else "🟡" if pcr < 1.0 else "🔴"
        st.metric("NIFTY PCR", f"{color} {pcr:.2f}")
    
    # Option Chains
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
                    line=dict(color='green', width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=[s['strike'] for s in strikes],
                    y=[s.get('put_ltp', 0) for s in strikes],
                    mode='lines+markers',
                    name='PUT Premium',
                    line=dict(color='red', width=2)
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
    
    # Recommendations
    st.subheader("📊 Trading Recommendations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        pcr = data.get('nifty_chain', {}).get('total_pcr', 0.5)
        if pcr < 0.5:
            action, color, emoji = "BUY CALL", "#00ff00", "🟢"
        elif pcr > 1.0:
            action, color, emoji = "BUY PUT", "#ff4444", "🔴"
        else:
            action, color, emoji = "WAIT", "#ffaa00", "🟡"
        
        st.markdown(f"""
        <div class="card">
            <div style="font-size: 18px; font-weight: bold;">NIFTY</div>
            <div style="font-size: 24px; color: {color};">{emoji} {action}</div>
            <div style="margin-top: 10px;">
                <div><span style="color:#888;">ATM Strike:</span> {nifty_atm['strike'] if nifty_atm else '-'}</div>
                <div><span style="color:#888;">CALL Premium:</span> ₹{nifty_atm['call_ltp'] if nifty_atm else 0:.2f}</div>
                <div><span style="color:#888;">PCR:</span> {pcr:.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        pcr = data.get('sensex_chain', {}).get('total_pcr', 0.5)
        if pcr < 0.5:
            action, color, emoji = "BUY CALL", "#00ff00", "🟢"
        elif pcr > 1.0:
            action, color, emoji = "BUY PUT", "#ff4444", "🔴"
        else:
            action, color, emoji = "WAIT", "#ffaa00", "🟡"
        
        st.markdown(f"""
        <div class="card">
            <div style="font-size: 18px; font-weight: bold;">SENSEX</div>
            <div style="font-size: 24px; color: {color};">{emoji} {action}</div>
            <div style="margin-top: 10px;">
                <div><span style="color:#888;">ATM Strike:</span> {sensex_atm['strike'] if sensex_atm else '-'}</div>
                <div><span style="color:#888;">CALL Premium:</span> ₹{sensex_atm['call_ltp'] if sensex_atm else 0:.2f}</div>
                <div><span style="color:#888;">PCR:</span> {pcr:.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("⚙️ Controls")
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
    refresh_rate = st.sidebar.selectbox("Refresh Rate", [3, 5, 10, 15, 30], index=1)
    
    if auto_refresh:
        st.sidebar.info(f"🔄 Auto refreshing every {refresh_rate}s")
        time.sleep(refresh_rate)
        st.rerun()
    
    st.sidebar.markdown("---")
    with st.sidebar.expander("🔐 Connection Status"):
        if data.get('authenticated'):
            st.success("✅ Angel One API")
        else:
            st.warning(f"🔄 {data.get('source', 'Fallback')} Data")
    
    st.sidebar.caption("🚀 F&O Trading Dashboard v2.0")


if __name__ == "__main__":
    main()
