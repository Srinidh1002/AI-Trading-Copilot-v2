import sqlite3

import pandas as pd
import streamlit as st
from services.market_snapshot import get_market_snapshot
from services.dashboard.dashboard_analysis_service import (
    DashboardAnalysisService,
    dashboard_trade_presentation,
)
from services.trade.paper_trade_manager import (
    get_trade_statistics,
)
from services.refresh.refresh_intervals import (
    MARKET_SNAPSHOT,
)
from services.performance import performance_monitor
from services.refresh import history_cache
from services.utils import safe_execute
from services.health import health_check
from config import (
    APP_NAME,
    VERSION,
    PHASE,
    BUILD,
)


DB = "database/ai_trading.db"
dashboard_analysis_service = DashboardAnalysisService()


def _metric_number(value):
    return round(value, 2) if isinstance(value, (int, float)) else "—"

def load_history(limit=25):

    try:

        conn = sqlite3.connect(DB)

        df = pd.read_sql_query(
            """
            SELECT
                timestamp,
                signal,
                confidence,
                price
            FROM decision_log
            ORDER BY id DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )

        conn.close()

        return df

    except Exception:

        return pd.DataFrame()


def load_validation_stats():

    return get_trade_statistics()

@st.fragment(run_every=MARKET_SNAPSHOT)
def home():

    snapshot = safe_execute(
        get_market_snapshot,
        default=None,
    )

    if snapshot is None:

        st.error(
            "Unable to load market snapshot. Please try again."
        )

        st.stop()

    analysis_result = safe_execute(
        dashboard_analysis_service.analyse,
        default=None,
        legacy_snapshot=snapshot,
    )

    trade = dashboard_trade_presentation(analysis_result) if analysis_result else None

    if trade is None:

        st.error(
            "Canonical dashboard analysis was unavailable; no trade is authorized."
        )

        st.stop()

    indicators = snapshot["indicators"]

    stats = safe_execute(
        load_validation_stats,
        default={
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "net_pnl": 0,
        },
    )

    option = snapshot.get("option_analysis", {})

    st.title("🤖 AI Trading Copilot V2")

    st.caption(
        f"Market : {snapshot['market_status']} | "
        f"Updated : {snapshot['refresh_time']}"
    )

    st.divider()

    # =====================================================
    # TOP SUMMARY
    # =====================================================

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "NIFTY",
        round(snapshot["ltp"], 2),
    )

    c2.metric(
        "Decision",
        trade["decision"],
    )

    c3.metric(
        "Confidence",
        f"{trade['confidence']}%",
    )

    c4.metric(
        "Institutional Score",
        trade["institutional_score"],
    )

    c5.metric(
        "Trade Grade",
        trade["trade_grade"],
    )

    c6.metric(
        "Execution",
        trade["trade_action"],
    )

    st.divider()

    # =====================================================
    # SCORES
    # =====================================================

    a, b, c, d = st.columns(4)

    try:
        a.metric("Bull Score", trade["bull_score"])
        b.metric("Bear Score", trade["bear_score"])
        c.metric("Neutral", trade["neutral_score"])
        d.metric("RSI", round(indicators["RSI"], 2))
    except Exception as e:
            st.exception(e)
            st.stop()

    st.divider()

    # =====================================================
    # TREND
    # =====================================================

    st.subheader("📊 Trend Analysis")

    x1, x2, x3 = st.columns(3)

    x1.metric(
        "Momentum",
        trade["trend"]["momentum"],
    )

    x2.metric(
        "Strength",
        trade["trend"]["strength"],
    )

    x3.metric(
        "Score",
        f"{trade['trend']['score']}%",
    )

    st.divider()

    # =====================================================
    # CANDLESTICK
    # =====================================================

    st.subheader("🕯 Candlestick")

    y1, y2, y3 = st.columns(3)

    y1.metric(
        "Pattern",
        trade["pattern"]["pattern"],
    )

    y2.metric(
        "Signal",
        trade["pattern"]["signal"],
    )

    y3.metric(
        "Status",
        "Detected",
    )

    st.divider()

    # =====================================================
    # SUPPORT / RESISTANCE
    # =====================================================

    st.subheader("📍 Support & Resistance")

    s1, s2 = st.columns(2)

    s1.metric(
        "Support",
        _metric_number(trade["support_resistance"]["Support"]),
    )

    s2.metric(
        "Resistance",
        _metric_number(trade["support_resistance"]["Resistance"]),
    )

    st.divider()

    # =====================================================
    # OPTION CHAIN ANALYSIS
    # =====================================================

    st.subheader("📈 Institutional Option Analysis")

    if option and option.get("Status") == "Success":

        flow = option.get("Flow", {})

        greeks = option.get("Greeks", {})

        summary = greeks.get("Summary", {})

        atm = greeks.get("ATM", {})

        # -------------------------------------------------

        o1, o2, o3, o4 = st.columns(4)

        o1.metric(
            "PCR",
            option["PCR"]["PCR"],
        )

        o2.metric(
            "Option Bias",
            option["Bias"],
        )

        o3.metric(
            "Option Flow",
            flow.get(
                "Flow",
                "-",
            ),
        )

        o4.metric(
            "Confidence",
            f"{option['Confidence']}%",
        )

        # -------------------------------------------------

        a1, a2, a3 = st.columns(3)

        a1.metric(
            "Support",
            option["Support"],
        )

        a2.metric(
            "Resistance",
            option["Resistance"],
        )

        a3.metric(
            "Max Pain",
            option["MaxPainStrike"],
        )

        st.divider()

        # -------------------------------------------------

        st.subheader("🏦 Open Interest")

        oi = option["OI"]

        i1, i2, i3 = st.columns(3)

        i1.metric(
            "CE OI",
            f"{oi['CE_OI']:,}",
        )

        i2.metric(
            "PE OI",
            f"{oi['PE_OI']:,}",
        )

        i3.metric(
            "PCR",
            oi["PCR"],
        )

        st.divider()

        # -------------------------------------------------

        st.subheader("📐 Live Greeks")

        g1, g2, g3, g4, g5 = st.columns(5)

        g1.metric(
            "Δ Delta",
            round(
                atm.get("Delta", 0),
                4,
            ),
        )

        g2.metric(
            "Γ Gamma",
            round(
                atm.get("Gamma", 0),
                4,
            ),
        )

        g3.metric(
            "Θ Theta",
            round(
                atm.get("Theta", 0),
                4,
            ),
        )

        g4.metric(
            "V Vega",
            round(
                atm.get("Vega", 0),
                4,
            ),
        )

        g5.metric(
            "IV %",
            round(
                atm.get("IV", 0),
                2,
            ),
        )

        st.divider()

        s1, s2, s3 = st.columns(3)

        s1.metric(
            "Greeks Bias",
            summary.get(
                "Bias",
                "-",
            ),
        )

        s2.metric(
            "Average Delta",
            summary.get(
                "AverageDelta",
                0,
            ),
        )

        s3.metric(
            "Average IV",
            summary.get(
                "AverageIV",
                0,
            ),
        )

    else:

        st.info(
            "Live option chain unavailable."
        )

    st.divider()

    # =====================================================
    # TRADE PLAN
    # =====================================================

    st.subheader("💰 Trade Plan")

    p1, p2, p3 = st.columns(3)

    p1.metric(
        "Entry",
        trade["entry"],
    )

    p1.metric(
        "Stop Loss",
        trade["stop_loss"],
    )

    p2.metric(
        "Target 1",
        trade["target1"],
    )

    p2.metric(
        "Target 2",
        trade["target2"],
    )

    p3.metric(
        "Target 3",
        trade["risk"]["TARGET3"],
    )

    p3.metric(
        "Risk : Reward",
        trade["risk"]["RR"],
    )

    st.divider()

    # =====================================================
    # INSTITUTIONAL SCORE
    # =====================================================

    st.subheader("🏛 Institutional Decision")

    t1, t2, t3 = st.columns(3)

    t1.metric(
        "Trade Grade",
        trade["trade_grade"],
    )

    t2.metric(
        "Institutional Score",
        trade["institutional_score"],
    )

    t3.metric(
        "Execution",
        trade["trade_action"],
    )

    st.caption(
        f"Risk Level : {trade['risk_level']}"
    )

    st.divider()

    # =====================================================
    # AI REASON
    # =====================================================

    st.subheader("🧠 AI Reason")

    st.success(
        trade["reason"]
    )

    if analysis_result and analysis_result.comparison:
        with st.expander("Canonical vs legacy diagnostics", expanded=False):
            st.caption(
                f"{len(analysis_result.comparison.differences)} semantic differences; "
                "diagnostic only."
            )

    st.divider()

    # =====================================================
    # VALIDATION
    # =====================================================

    st.subheader("📈 Validation")

    v1, v2, v3, v4, v5 = st.columns(5)

    v1.metric(
        "Trades",
        stats["total_trades"],
    )

    v2.metric(
        "Wins",
        stats["winning_trades"],
    )

    v3.metric(
        "Losses",
        stats["losing_trades"],
    )

    v4.metric(
        "Net PnL",
        stats["net_pnl"],
    )

    v5.metric(
        "Trade Grade",
        trade["trade_grade"],
    )

    st.divider()

    # =====================================================
    # PERFORMANCE METRICS
    # =====================================================

    with st.expander("⚡ Performance Metrics", expanded=False):

        col1, col2 = st.columns(2)

        with col1:

            st.metric(
                "Market Snapshot",
                f"{performance_monitor.elapsed('market_snapshot')} sec",
            )

        with col2:

            st.metric(
                "Decision Engine",
                f"{performance_monitor.elapsed('decision_engine')} sec",
            )

    st.divider()
    # =====================================================
    # SYSTEM HEALTH
    # =====================================================

    health = health_check.run()

    with st.expander("🟢 System Health", expanded=False):

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Market",
            health["market_snapshot"],
        )

        c2.metric(
            "Database",
            health["database"],
        )

        c3.metric(
            "Paper Trade",
            health["paper_trade"],
        )

        c4.metric(
            "Option Chain",
            health["option_chain"],
        )

    st.divider()
    # =====================================================
    # DECISION HISTORY
    # =====================================================

    st.subheader("📜 Decision History")

    history = safe_execute(
        history_cache.get,
        default=pd.DataFrame(),
        loader=load_history,
    )

    if history.empty:

        st.info(
            "No trade history available."
        )

    else:

        st.dataframe(
            history,
            width="stretch",
            hide_index=True,
        )

        st.divider()

        st.caption(
            f"{APP_NAME} | "
            f"Version {VERSION} | "
            f"{PHASE} | "
            f"Build {BUILD}"
        )
