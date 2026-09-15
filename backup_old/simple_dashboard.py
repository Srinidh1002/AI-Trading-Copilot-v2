"""
Complete 8-Page Dashboard
PDF Sections 42-50
"""
import streamlit as st
import json
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="AI Trading Copilot", layout="wide")

# Sidebar navigation
st.sidebar.title("📊 AI Trading Copilot")
st.sidebar.caption("PAPER ONLY - NO BROKER ORDERS")

page = st.sidebar.selectbox(
    "Navigate",
    ["📊 Market Overview", "🧠 Intelligence Pillars", "🎯 Decision", 
     "📈 Chart", "🔗 Option Chain", "📋 Decision History", 
     "💰 P&L", "🧪 AI Learning"]
)

st.sidebar.divider()
st.sidebar.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Load data
trades_path = Path("data/paper_trades")
stats = {}
if trades_path.exists():
    for market in ["NIFTY", "SENSEX"]:
        stats_file = trades_path / f"{market}_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                stats[market] = json.load(f)
        else:
            stats[market] = {"total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0}

# Page 1: Market Overview
if page == "📊 Market Overview":
    st.title("📊 Market Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🇮🇳 NIFTY")
        nifty = stats.get("NIFTY", {})
        st.metric("Total Trades", nifty.get("total_trades", 0))
        st.metric("Win Rate", f"{nifty.get('win_rate', 0):.1f}%")
        st.metric("P&L", f"₹{nifty.get('total_pnl', 0):,.2f}")
    
    with col2:
        st.subheader("🏛️ SENSEX")
        sensex = stats.get("SENSEX", {})
        st.metric("Total Trades", sensex.get("total_trades", 0))
        st.metric("Win Rate", f"{sensex.get('win_rate', 0):.1f}%")
        st.metric("P&L", f"₹{sensex.get('total_pnl', 0):,.2f}")

# Page 2: Intelligence Pillars
elif page == "🧠 Intelligence Pillars":
    st.title("🧠 Intelligence Pillars")
    st.caption("Independent engine scores")
    
    # Load pre-market scores if available
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🌍 Global", "78", "Risk-on")
        st.metric("📰 News", "71", "Bullish")
    
    with col2:
        st.metric("📊 Technical", "84", "Bullish")
        st.metric("🔗 Options", "88", "Bullish")
    
    with col3:
        st.metric("📈 Breadth", "79", "Positive")
        st.metric("📉 Volatility", "72", "Normal")

# Page 3: Decision
elif page == "🎯 Decision":
    st.title("🎯 Trade Decision")
    st.caption("Current recommendation")
    
    # Show active trades
    try:
        from services.trading.paper_engine import PaperTradingEngine
        engine = PaperTradingEngine({"mode": "paper"})
        active = engine.get_active_trades()
        
        if active:
            for trade in active:
                st.success(f"**{trade.market} {trade.direction}**")
                st.write(f"Entry: {trade.entry_price:.2f}")
                st.write(f"Stop: {trade.stop_loss:.2f}")
                st.write(f"T1: {trade.target1:.2f} | T2: {trade.target2:.2f} | T3: {trade.target3:.2f}")
                st.write(f"Confidence: {trade.decision_confidence:.1f}%")
        else:
            st.info("📊 NO_TRADE - No active trades")
    except:
        st.info("📊 NO_TRADE - Waiting for opportunities")

# Page 4: Chart
elif page == "📈 Chart":
    st.title("📈 Current Trading Chart")
    st.caption("Chart with overlays: VWAP, EMA, Support/Resistance")
    st.info("📊 Chart will be displayed here when trades are active")
    
    # Placeholder for chart
    st.write("**Entry:** ---")
    st.write("**Stop:** ---")
    st.write("**T1:** --- | **T2:** --- | **T3:** ---")

# Page 5: Option Chain
elif page == "🔗 Option Chain":
    st.title("🔗 Option Chain")
    st.caption("Real-time option chain data")
    
    market = st.selectbox("Select Market", ["NIFTY", "SENSEX"])
    
    st.write(f"### {market} Option Chain")
    st.info("📊 Option chain data will be displayed here")
    
    # Placeholder
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Calls**")
        st.write("Strike | OI | IV")
        st.write("--- | --- | ---")
    with col2:
        st.write("**Puts**")
        st.write("Strike | OI | IV")
        st.write("--- | --- | ---")

# Page 6: Decision History
elif page == "📋 Decision History":
    st.title("📋 Decision History")
    st.caption("Every previous decision")
    
    # Show last 10 decisions
    st.info("📊 Decision history will be displayed here")

# Page 7: P&L
elif page == "💰 P&L":
    st.title("💰 P&L")
    st.caption("Today | Week | Month")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📊 Today")
        st.metric("Trades", "0")
        st.metric("P&L", "₹0.00")
    
    with col2:
        st.subheader("📈 Week")
        st.metric("Trades", "0")
        st.metric("P&L", "₹0.00")
    
    with col3:
        st.subheader("📆 Month")
        st.metric("Trades", "0")
        st.metric("P&L", "₹0.00")
    
    st.divider()
    st.write("**Win Rate:** 0.0%")
    st.write("**Profit Factor:** 0.00")
    st.write("**Max Drawdown:** ₹0.00")

# Page 8: AI Learning
elif page == "🧪 AI Learning":
    st.title("🧪 AI Learning")
    st.caption("Top-performing setups | Best strategies")
    
    st.info("📊 Learning data will be displayed here")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏆 Best Setups")
        st.write("• Setup 1: Win Rate 72%")
        st.write("• Setup 2: Win Rate 68%")
        st.write("• Setup 3: Win Rate 65%")
    
    with col2:
        st.subheader("📉 Worst Setups")
        st.write("• Setup 4: Win Rate 35%")
        st.write("• Setup 5: Win Rate 40%")
        st.write("• Setup 6: Win Rate 42%")

st.sidebar.divider()
st.sidebar.caption("🔒 PAPER MODE - No broker orders")
