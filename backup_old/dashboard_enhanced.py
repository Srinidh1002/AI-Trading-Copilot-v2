"""
Enhanced Dashboard - 8 Pages + Capital Input
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

st.set_page_config(page_title="AI Trading Copilot", layout="wide")

# ============================================================
# SESSION STATE
# ============================================================

if "capital" not in st.session_state:
    st.session_state.capital = 100000.0

if "risk_percent" not in st.session_state:
    st.session_state.risk_percent = 2.0

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("AI Trading Copilot")
st.sidebar.caption("PAPER ONLY - NO BROKER ORDERS")

# Capital Input
st.sidebar.subheader("Capital Management")
capital_input = st.sidebar.number_input(
    "Deployable Capital (Rs)",
    min_value=1000.0,
    max_value=10000000.0,
    value=st.session_state.capital,
    step=10000.0,
    format="%.0f"
)
st.session_state.capital = capital_input

risk_percent = st.sidebar.slider(
    "Risk per Trade (%)",
    min_value=0.5,
    max_value=5.0,
    value=st.session_state.risk_percent,
    step=0.5
)
st.session_state.risk_percent = risk_percent

# Show capital info
st.sidebar.divider()
max_risk = capital_input * (risk_percent / 100)
st.sidebar.metric("Max Risk per Trade", f"Rs {max_risk:,.2f}")
st.sidebar.caption(f"Based on {risk_percent}% risk")

# Navigation
st.sidebar.divider()
page = st.sidebar.selectbox(
    "Navigate",
    ["Market Overview", "Pre-Market Intelligence", "Decision",
     "Chart", "Option Chain", "Decision History",
     "P&L Reports", "AI Learning"]
)

# ============================================================
# LOAD DATA
# ============================================================

def load_data():
    """Load all data from files."""
    data = {
        "stats": {},
        "trades": [],
        "pre_market": {},
        "active_trades": []
    }
    
    trades_path = Path("data/paper_trades")
    if trades_path.exists():
        for market in ["NIFTY", "SENSEX"]:
            stats_file = trades_path / f"{market}_stats.json"
            if stats_file.exists():
                with open(stats_file) as f:
                    data["stats"][market] = json.load(f)
    
    cert_path = Path("data/certification")
    if cert_path.exists():
        for market in ["NIFTY", "SENSEX"]:
            stats_file = cert_path / f"{market}_stats.json"
            if stats_file.exists():
                with open(stats_file) as f:
                    data[f"cert_{market}"] = json.load(f)
    
    try:
        from services.trading.paper_engine import PaperTradingEngine
        engine = PaperTradingEngine({"mode": "paper"})
        data["active_trades"] = engine.get_active_trades()
    except:
        pass
    
    return data

# ============================================================
# PAGE 1: MARKET OVERVIEW
# ============================================================

def page_market_overview(data):
    st.title("Market Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("NIFTY")
        nifty = data.get("stats", {}).get("NIFTY", {})
        st.metric("Total Trades", nifty.get("total_trades", 0))
        st.metric("Win Rate", f"{nifty.get('win_rate', 0):.1f}%")
        st.metric("P&L", f"Rs {nifty.get('total_pnl', 0):,.2f}")
        st.metric("Profit Factor", f"{nifty.get('profit_factor', 0):.2f}")
        
        cert_nifty = data.get("cert_NIFTY", {})
        if cert_nifty:
            progress = cert_nifty.get("countable_trades", 0)
            target = cert_nifty.get("target_trades", 100)
            st.progress(progress / target if target > 0 else 0)
            st.caption(f"Certification: {progress}/{target}")
    
    with col2:
        st.subheader("SENSEX")
        sensex = data.get("stats", {}).get("SENSEX", {})
        st.metric("Total Trades", sensex.get("total_trades", 0))
        st.metric("Win Rate", f"{sensex.get('win_rate', 0):.1f}%")
        st.metric("P&L", f"Rs {sensex.get('total_pnl', 0):,.2f}")
        st.metric("Profit Factor", f"{sensex.get('profit_factor', 0):.2f}")
        
        cert_sensex = data.get("cert_SENSEX", {})
        if cert_sensex:
            progress = cert_sensex.get("countable_trades", 0)
            target = cert_sensex.get("target_trades", 100)
            st.progress(progress / target if target > 0 else 0)
            st.caption(f"Certification: {progress}/{target}")
    
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    capital = st.session_state.capital
    risk = capital * (st.session_state.risk_percent / 100)
    
    col1.metric("Capital", f"Rs {capital:,.0f}")
    col2.metric("Risk per Trade", f"Rs {risk:,.2f}")
    col3.metric("Max Loss", f"Rs {risk * 2:,.2f}")
    col4.metric("Suggested Lot Size", "1-2 lots")

# ============================================================
# PAGE 2: PRE-MARKET INTELLIGENCE
# ============================================================

def page_pre_market(data):
    st.title("Pre-Market Intelligence")
    st.caption("All 8 pillars - Real-time scores")
    
    try:
        from services.analysis.pre_market_intelligence import analyze_pre_market
        from services.analysis.external_data import get_external_data
        
        external = get_external_data()
        
        vix = external.get_vix()
        fii = external.get_fii_dii()
        events = external.get_economic_events()
        news = external.get_news("NIFTY")
        news_sentiment = external.analyze_news_sentiment("NIFTY")
        
        pre_market = analyze_pre_market({
            "vix": vix.get("value", 15),
            "fii_dii": fii,
            "economic_events": events,
            "news": news,
            "news_sentiment": news_sentiment.get("sentiment", 0)
        })
        
        pillars = pre_market.get("pillars", {})
        overall = pre_market.get("overall_score", 50)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Overall Score", f"{overall:.1f}/100")
        col2.metric("Status", pre_market.get("status", "UNKNOWN"))
        col3.metric("Blockers", len(pre_market.get("blockers", [])))
        
        st.divider()
        
        cols = st.columns(4)
        
        pillar_data = [
            ("Global", pillars.get("global", {}).get("score", 50)),
            ("News", pillars.get("news", {}).get("score", 50)),
            ("Institutional", pillars.get("institutional", {}).get("score", 50)),
            ("Previous Session", pillars.get("previous_session", {}).get("score", 50)),
            ("Option Chain", pillars.get("option_chain", {}).get("score", 50)),
            ("VIX", pillars.get("vix", {}).get("score", 50)),
            ("Regime", pillars.get("regime", {}).get("score", 50)),
            ("Economic", pillars.get("economic", {}).get("score", 50)),
        ]
        
        for i, (name, score) in enumerate(pillar_data):
            col = cols[i % 4]
            color = "green" if score >= 60 else "yellow" if score >= 40 else "red"
            col.metric(name, f"{color} {score:.0f}/100")
        
        st.divider()
        st.subheader("Reasons")
        for reason in pre_market.get("reasons", [])[:10]:
            st.write(f"• {reason}")
        
        if pre_market.get("blockers"):
            st.warning("Blockers:")
            for blocker in pre_market.get("blockers", []):
                st.write(f"  • {blocker}")
        
    except Exception as e:
        st.error(f"Could not load pre-market data: {e}")

# ============================================================
# PAGE 3: DECISION
# ============================================================

def page_decision(data):
    st.title("Trade Decision")
    st.caption("Current recommendation with capital-based sizing")
    
    capital = st.session_state.capital
    risk_percent = st.session_state.risk_percent
    
    active = data.get("active_trades", [])
    
    if active:
        st.success(f"{len(active)} Active Trade(s)")
        
        for trade in active:
            st.write(f"### {trade.market} {trade.direction}")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Entry", f"Rs {trade.entry_price:,.2f}")
            col2.metric("Stop", f"Rs {trade.stop_loss:,.2f}")
            col3.metric("Confidence", f"{trade.decision_confidence:.1f}%")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("T1", f"Rs {trade.target1:,.2f} (+15%)")
            col2.metric("T2", f"Rs {trade.target2:,.2f} (+30%)")
            col3.metric("T3", f"Rs {trade.target3:,.2f} (+50%)")
            
            risk_per_trade = capital * (risk_percent / 100)
            st.info(f"Capital: Rs {capital:,.0f} | Risk: {risk_percent}% | Max Loss: Rs {risk_per_trade:,.2f}")
            
            premium = trade.premium or 100
            suggested_lots = int(risk_per_trade / (premium * 1.5))
            suggested_lots = max(1, min(suggested_lots, 3))
            st.caption(f"Suggested Quantity: {suggested_lots} lots (Premium: Rs {premium:.2f})")
    else:
        st.info("NO_TRADE - No active trades")
        
        st.write("### Market Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            nifty_stats = data.get("stats", {}).get("NIFTY", {})
            st.write(f"NIFTY: {nifty_stats.get('total_trades', 0)} trades")
        
        with col2:
            sensex_stats = data.get("stats", {}).get("SENSEX", {})
            st.write(f"SENSEX: {sensex_stats.get('total_trades', 0)} trades")

# ============================================================
# PAGE 4: CHART
# ============================================================

def page_chart():
    st.title("Trading Chart")
    st.caption("Price with VWAP, EMA, Support/Resistance")
    
    st.info("Chart will be displayed here when trades are active")
    
    st.write("**Entry:** ---")
    st.write("**Stop:** ---")
    st.write("**T1:** --- | **T2:** --- | **T3:** ---")
    
    capital = st.session_state.capital
    st.caption(f"Capital: Rs {capital:,.0f}")

# ============================================================
# PAGE 5: OPTION CHAIN
# ============================================================

def page_option_chain():
    st.title("Option Chain")
    st.caption("Real-time option chain data")
    
    market = st.selectbox("Select Market", ["NIFTY", "SENSEX"])
    
    st.info(f"{market} Option Chain data will be displayed here")

# ============================================================
# PAGE 6: DECISION HISTORY
# ============================================================

def page_decision_history():
    st.title("Decision History")
    st.caption("Every previous decision")
    
    try:
        from services.certification.certification_engine import CertificationEngine
        cert = CertificationEngine({"markets": ["NIFTY", "SENSEX"]})
        
        for market in ["NIFTY", "SENSEX"]:
            stats = cert.get_stats(market)
            if stats:
                st.write(f"### {market}")
                st.write(f"Countable Trades: {stats.countable_trades}/{stats.target_trades}")
                st.write(f"Wins: {stats.wins} | Losses: {stats.losses}")
                st.write(f"Win Rate: {stats.win_rate:.1f}%")
                st.write(f"Total P&L: Rs {stats.total_pnl:,.2f}")
                st.divider()
    except:
        st.info("No decision history available")

# ============================================================
# PAGE 7: P&L REPORTS
# ============================================================

def page_pnl(data):
    st.title("P&L Reports")
    st.caption("Today | Week | Month")
    
    st.subheader("Today")
    col1, col2, col3 = st.columns(3)
    
    nifty = data.get("stats", {}).get("NIFTY", {})
    sensex = data.get("stats", {}).get("SENSEX", {})
    total_trades = nifty.get("total_trades", 0) + sensex.get("total_trades", 0)
    total_pnl = nifty.get("total_pnl", 0) + sensex.get("total_pnl", 0)
    
    col1.metric("Total Trades", total_trades)
    col2.metric("P&L", f"Rs {total_pnl:,.2f}")
    col3.metric("Win Rate", f"{((nifty.get('wins', 0) + sensex.get('wins', 0)) / max(1, total_trades) * 100):.1f}%")
    
    st.subheader("Week")
    col1, col2, col3 = st.columns(3)
    col1.metric("Trades", total_trades)
    col2.metric("P&L", f"Rs {total_pnl:,.2f}")
    col3.metric("Profit Factor", f"{nifty.get('profit_factor', 0) + sensex.get('profit_factor', 0):.2f}")
    
    st.subheader("Month")
    col1, col2, col3 = st.columns(3)
    col1.metric("Trades", total_trades)
    col2.metric("P&L", f"Rs {total_pnl:,.2f}")
    col3.metric("Max Drawdown", f"Rs {nifty.get('max_drawdown', 0) + sensex.get('max_drawdown', 0):,.2f}")
    
    st.divider()
    capital = st.session_state.capital
    risk = capital * (st.session_state.risk_percent / 100)
    st.caption(f"Capital: Rs {capital:,.0f} | Risk per Trade: Rs {risk:,.2f} | Daily Loss Limit: Rs {risk * 3:,.2f}")

# ============================================================
# PAGE 8: AI LEARNING
# ============================================================

def page_learning():
    st.title("AI Learning")
    st.caption("Top-performing setups | Best strategies")
    
    st.info("Learning data will be displayed here as trades complete")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Best Setups")
        st.write("• Setup 1: Win Rate 72%")
        st.write("• Setup 2: Win Rate 68%")
        st.write("• Setup 3: Win Rate 65%")
    
    with col2:
        st.subheader("Worst Setups")
        st.write("• Setup 4: Win Rate 35%")
        st.write("• Setup 5: Win Rate 40%")
        st.write("• Setup 6: Win Rate 42%")

# ============================================================
# MAIN
# ============================================================

def main():
    """Main dashboard."""
    data = load_data()
    
    now = datetime.now()
    st.sidebar.caption(f"{now.strftime('%H:%M:%S')}")
    
    if page == "Market Overview":
        page_market_overview(data)
    elif page == "Pre-Market Intelligence":
        page_pre_market(data)
    elif page == "Decision":
        page_decision(data)
    elif page == "Chart":
        page_chart()
    elif page == "Option Chain":
        page_option_chain()
    elif page == "Decision History":
        page_decision_history()
    elif page == "P&L Reports":
        page_pnl(data)
    elif page == "AI Learning":
        page_learning()

if __name__ == "__main__":
    main()
