# dashboard_real.py - LIVE DASHBOARD WITH REAL DATA FROM ANGEL ONE

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import sys
import os
from datetime import datetime
import pytz
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="F&O Trading Dashboard - Real Data",
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
    </style>
""", unsafe_allow_html=True)


def get_real_data():
    """Get REAL data from Angel One API."""
    try:
        from services.market.angel_one_api import AngelOneAPI
        
        api = AngelOneAPI()
        
        if api.authenticate():
            data = {
                'nifty_ltp': api.get_ltp('NIFTY'),
                'sensex_ltp': api.get_ltp('SENSEX'),
                'nifty_chain': api.get_option_chain('NIFTY'),
                'sensex_chain': api.get_option_chain('SENSEX'),
                'timestamp': datetime.now().isoformat(),
                'authenticated': True
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
        return {'error': str(e)}
    
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
    st.title("📈 F&O Trading Dashboard - Real Data")
    st.caption(f"Live Data from Angel One | {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S IST')}")
    
    # Refresh button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 Refresh"):
            st.rerun()
    
    # Get real data
    data = get_real_data()
    
    if data and 'error' not in data and data.get('authenticated'):
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
                    
                    # Add PCR as bar chart
                    fig.add_trace(go.Bar(
                        x=[s['strike'] for s in strikes],
                        y=[s.get('pcr', 0) for s in strikes],
                        name='PCR',
                        yaxis='y2',
                        marker_color='yellow',
                        opacity=0.3
                    ))
                    
                    fig.update_layout(
                        title="Option Premiums by Strike",
                        xaxis_title="Strike Price",
                        yaxis_title="Premium (₹)",
                        yaxis2=dict(title="PCR", overlaying='y', side='right', range=[0, 2]),
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
                strike = nifty_atm.get('strike', 0)
                premium = nifty_atm.get('call_ltp', 0)
            elif pcr > 1.0:
                action = "BUY PUT"
                color = "#ff4444"
                emoji = "🔴"
                strike = nifty_atm.get('strike', 0)
                premium = nifty_atm.get('put_ltp', 0)
            else:
                action = "WAIT"
                color = "#ffaa00"
                emoji = "🟡"
                strike = 0
                premium = 0
            
            st.markdown(f"""
            <div class="card">
                <div style="font-size: 18px; font-weight: bold;">NIFTY</div>
                <div style="font-size: 24px; color: {color};">
                    {emoji} {action}
                </div>
                <div style="margin-top: 10px;">
                    <div><span style="color:#888;">Strike:</span> {strike}</div>
                    <div><span style="color:#888;">Premium:</span> ₹{premium:.2f}</div>
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
                strike = sensex_atm.get('strike', 0)
                premium = sensex_atm.get('call_ltp', 0)
            elif pcr > 1.0:
                action = "BUY PUT"
                color = "#ff4444"
                emoji = "🔴"
                strike = sensex_atm.get('strike', 0)
                premium = sensex_atm.get('put_ltp', 0)
            else:
                action = "WAIT"
                color = "#ffaa00"
                emoji = "🟡"
                strike = 0
                premium = 0
            
            st.markdown(f"""
            <div class="card">
                <div style="font-size: 18px; font-weight: bold;">SENSEX</div>
                <div style="font-size: 24px; color: {color};">
                    {emoji} {action}
                </div>
                <div style="margin-top: 10px;">
                    <div><span style="color:#888;">Strike:</span> {strike}</div>
                    <div><span style="color:#888;">Premium:</span> ₹{premium:.2f}</div>
                    <div><span style="color:#888;">PCR:</span> {pcr:.2f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    elif data and 'error' in data:
        st.error(f"❌ Error: {data['error']}")
        st.info("Please check your .env file has the correct Angel One credentials:")
        st.code("""
        ANGEL_APIKEY=your_api_key
        ANGEL_CLIENT_ID=your_client_id  
        ANGEL_PIN=your_pin
        ANGEL_TOTP_SECRET=your_totp
        """)
    else:
        st.warning("⏳ Waiting for data from Angel One...")
    
    # ===== SIDEBAR =====
    st.sidebar.title("⚙️ Controls")
    
    auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
    refresh_rate = st.sidebar.selectbox("Refresh Rate (seconds)", [3, 5, 10, 15, 30], index=1)
    
    if auto_refresh:
        st.sidebar.info(f"🔄 Auto refreshing every {refresh_rate} seconds")
        time.sleep(refresh_rate)
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("🚀 F&O Trading Dashboard v2.0")
    st.sidebar.caption("Powered by Angel One API")
    
    # Show credentials status
    with st.sidebar.expander("🔐 Connection Status"):
        if data and data.get('authenticated'):
            st.success("✅ Connected to Angel One")
        else:
            st.error("❌ Not connected")


if __name__ == "__main__":
    main()
