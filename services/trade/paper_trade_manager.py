"""
Paper Trade Manager V1
"""

import sqlite3
from datetime import datetime
from database import db_manager
DB = "database/ai_trading.db"


# ==========================================================
# SAVE TRADE
# ==========================================================

def save_trade(trade):

    with db_manager.session() as conn:

        cursor = conn.cursor()

    cursor.execute("""

        SELECT COUNT(*)

        FROM paper_trades

        WHERE status='OPEN'

    """)

    if cursor.fetchone()[0] > 0:

        conn.close()

        return

    cursor.execute("""

        INSERT INTO paper_trades(

            timestamp,

            signal,

            status,

            entry,

            stop_loss,

            target1,

            target2,

            exit_price,

            pnl,

            confidence,

            reason,

            duration

        )

        VALUES(

            ?,?,?,?,?,?,
            ?,?,?,?,?,?

        )

    """, (

        trade["timestamp"],

        trade["decision"],

        "OPEN",

        trade["entry"],

        trade["stop_loss"],

        trade["target1"],

        trade["target2"],

        None,

        None,

        trade["confidence"],

        trade["reason"],

        ""

    ))




# ==========================================================
# UPDATE OPEN TRADE
# ==========================================================

def update_open_trade(current_price):

    with db_manager.session() as conn:
       cursor = conn.cursor()

    cursor.execute("""

        SELECT

            id,

            signal,

            entry,

            stop_loss,

            target1

        FROM paper_trades

        WHERE status='OPEN'

        LIMIT 1

    """)

    row = cursor.fetchone()

    if row is None:

        conn.close()

        return

    trade_id, signal, entry, stop_loss, target1 = row

    close_trade = False

    pnl = 0

    exit_reason = ""

    if signal == "BUY":

        if current_price >= target1:

            pnl = current_price - entry

            exit_reason = "TARGET"

            close_trade = True

        elif current_price <= stop_loss:

            pnl = current_price - entry

            exit_reason = "STOP LOSS"

            close_trade = True

    elif signal == "SELL":

        if current_price <= target1:

            pnl = entry - current_price

            exit_reason = "TARGET"

            close_trade = True

        elif current_price >= stop_loss:

            pnl = entry - current_price

            exit_reason = "STOP LOSS"

            close_trade = True

    if close_trade:

        cursor.execute("""

            UPDATE paper_trades

            SET

                status='CLOSED',

                exit_price=?,

                pnl=?,

                reason=?,

                duration=

                CAST(

                    (

                        julianday('now')

                        -

                        julianday(timestamp)

                    )*24*60

                    AS INTEGER

                )

                || ' min'

            WHERE id=?

        """, (

            round(current_price,2),

            round(pnl,2),

            exit_reason,

            trade_id

        ))


# ==========================================================
# GET OPEN TRADE
# ==========================================================

def get_open_trade():

    conn = db_manager.connect()

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""

        SELECT *

        FROM paper_trades

        WHERE status='OPEN'

        LIMIT 1

    """)

    row = cursor.fetchone()

    conn.close()

    if row is None:

        return None

    return dict(row)


# ==========================================================
# TRADE STATISTICS
# ==========================================================

def get_trade_statistics():

    with db_manager.session() as conn:
        cursor = conn.cursor()

    cursor.execute("""

        SELECT

            COUNT(*),

            SUM(

                CASE

                    WHEN pnl>0 THEN 1

                    ELSE 0

                END

            ),

            SUM(

                CASE

                    WHEN pnl<0 THEN 1

                    ELSE 0

                END

            ),

            ROUND(

                IFNULL(SUM(pnl),0),

                2

            )

        FROM paper_trades

        WHERE status='CLOSED'

    """)

    total, wins, losses, net = cursor.fetchone()

    conn.close()

    return {

        "total_trades": total or 0,

        "winning_trades": wins or 0,

        "losing_trades": losses or 0,

        "net_pnl": net or 0

    }
