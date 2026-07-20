from pprint import pprint
import sqlite3

from services.ai_engine import ai_engine
from services.technical import technical_score


def show_last_decision():

    conn = sqlite3.connect("database/ai_trading.db")

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            timestamp,
            signal,
            confidence,
            price,
            bull_score,
            bear_score
        FROM decision_log
        ORDER BY id DESC
        LIMIT 1
        """
    )

    row = cursor.fetchone()

    conn.close()

    print("\n")
    print("=" * 70)
    print("LAST SAVED DECISION")
    print("=" * 70)

    if row:

        print(f"Time       : {row[0]}")
        print(f"Signal     : {row[1]}")
        print(f"Confidence : {row[2]}")
        print(f"Price      : {row[3]}")
        print(f"Bull Score : {row[4]}")
        print(f"Bear Score : {row[5]}")

    else:

        print("No decisions logged.")


def main():

    technical = technical_score()

    result = ai_engine(technical)

    print("\n")
    print("=" * 70)
    print("AI ENGINE")
    print("=" * 70)

    pprint(result)

    show_last_decision()


if __name__ == "__main__":
    main()