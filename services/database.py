"""
Database Manager V2
"""

import sqlite3
from pathlib import Path

DB_DIR = Path("database")
DB_DIR.mkdir(exist_ok=True)

DB = DB_DIR / "ai_trading.db"


# ==========================================================
# CONNECTION
# ==========================================================

def get_connection():

    conn = sqlite3.connect(DB)

    conn.row_factory = sqlite3.Row

    return conn


# ==========================================================
# INITIALIZE DATABASE
# ==========================================================

def initialize_database():

    conn = get_connection()

    cursor = conn.cursor()

    # ======================================================
    # Decision Log
    # ======================================================

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS decision_log(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        timestamp TEXT,

        symbol TEXT,

        price REAL,

        signal TEXT,

        confidence REAL,

        bull_score REAL,

        bear_score REAL,

        neutral_score REAL,

        entry REAL,

        stop_loss REAL,

        target1 REAL,

        target2 REAL,

        support REAL,

        resistance REAL,

        trend TEXT,

        pattern TEXT,

        reason TEXT,

        rsi REAL,

        adx REAL,

        atr REAL,

        ema20 REAL,

        ema50 REAL,

        ema200 REAL,

        macd REAL,

        macd_signal REAL,

        vwap REAL

    )

    """)

    # ======================================================
    # Paper Trades
    # ======================================================

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS paper_trades(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        timestamp TEXT,

        signal TEXT,

        status TEXT,

        entry REAL,

        stop_loss REAL,

        target1 REAL,

        target2 REAL,

        exit_price REAL,

        pnl REAL,

        confidence REAL,

        reason TEXT,

        duration TEXT

    )

    """)

    # ======================================================
    # Learning
    # ======================================================

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS learning(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        timestamp TEXT,

        signal TEXT,

        outcome TEXT,

        confidence REAL,

        reason TEXT

    )

    """)

    conn.commit()

    conn.close()


# ==========================================================
# LOG DECISION
# ==========================================================

def log_decision(data):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""

        SELECT

            signal,

            price,

            confidence

        FROM decision_log

        ORDER BY id DESC

        LIMIT 1

    """)

    last = cursor.fetchone()

    if last:

        if (

            last["signal"] == data["signal"]

            and

            abs(last["price"] - data["price"]) <= 0.10

            and

            abs(last["confidence"] - data["confidence"]) <= 1

        ):

            conn.close()

            return

    cursor.execute("""

        INSERT INTO decision_log(

            timestamp,

            symbol,

            price,

            signal,

            confidence,

            bull_score,

            bear_score,

            neutral_score,

            entry,

            stop_loss,

            target1,

            target2,

            support,

            resistance,

            trend,

            pattern,

            reason,

            rsi,

            adx,

            atr,

            ema20,

            ema50,

            ema200,

            macd,

            macd_signal,

            vwap

        )

        VALUES(

            ?,?,?,?,?,?,
            ?,?,?,?,?,?,
            ?,?,?,?,?,?,
            ?,?,?,?,?,?,
            ?,?

        )

    """, (

        data["timestamp"],

        data["symbol"],

        data["price"],

        data["signal"],

        data["confidence"],

        data["bull_score"],

        data["bear_score"],

        data["neutral_score"],

        data["entry"],

        data["stop_loss"],

        data["target1"],

        data["target2"],

        data["support"],

        data["resistance"],

        data["trend"],

        data["pattern"],

        data["reason"],

        data["rsi"],

        data["adx"],

        data["atr"],

        data["ema20"],

        data["ema50"],

        data["ema200"],

        data["macd"],

        data["macd_signal"],

        data["vwap"]

    ))

    conn.commit()

    conn.close()


initialize_database()