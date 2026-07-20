"""
database_v2.py
Starter database manager.
"""
import sqlite3
from pathlib import Path

DB = "database/ai_trading.db"
Path("database").mkdir(exist_ok=True)

def get_connection():
    return sqlite3.connect(DB)

def initialize_database():
    conn=get_connection()
    cur=conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS decision_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT,symbol TEXT,price REAL,signal TEXT,
      confidence REAL,bull_score REAL,bear_score REAL,
      entry REAL,stop_loss REAL,target1 REAL,target2 REAL,
      support REAL,resistance REAL,rsi REAL,adx REAL,atr REAL,
      ema20 REAL,ema50 REAL,ema200 REAL,macd REAL,macd_signal REAL)
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS paper_trades(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT,signal TEXT,status TEXT,
      entry REAL,stop_loss REAL,target1 REAL,target2 REAL,
      exit_price REAL,pnl REAL,confidence REAL,reason TEXT,duration TEXT)
    """)
    conn.commit()
    conn.close()

def get_last_signal():
    conn=get_connection()
    cur=conn.cursor()
    cur.execute("SELECT signal FROM decision_log ORDER BY id DESC LIMIT 1")
    r=cur.fetchone()
    conn.close()
    return r[0] if r else None

def log_decision(data):
    conn=get_connection()
    cur=conn.cursor()
    cur.execute("""
    INSERT INTO decision_log(
    timestamp,symbol,price,signal,confidence,bull_score,bear_score,
    entry,stop_loss,target1,target2,support,resistance,rsi,adx,atr,
    ema20,ema50,ema200,macd,macd_signal)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(
        data["timestamp"],data["symbol"],data["price"],data["signal"],
        data["confidence"],data["bull_score"],data["bear_score"],
        data["entry"],data["stop_loss"],data["target1"],data["target2"],
        data["support"],data["resistance"],data["rsi"],data["adx"],
        data["atr"],data["ema20"],data["ema50"],data["ema200"],
        data["macd"],data["macd_signal"]))
    conn.commit()
    conn.close()

initialize_database()
