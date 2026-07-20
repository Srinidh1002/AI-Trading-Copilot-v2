from pprint import pprint

from services.broker.session_manager import SessionManager


def main():

    session = SessionManager()

    print("\n")
    print("=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)

    pprint(session.summary())

    print("\n")
    print("=" * 70)
    print("LIVE NIFTY")
    print("=" * 70)

    data = session.execute(
        session.client.ltp,
        "NSE",
        "NIFTY",
        "99926000",
    )

    pprint(data)


if __name__ == "__main__":
    main()