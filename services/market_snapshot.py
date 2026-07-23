"""
Market Snapshot Service V3

Uses the centralized MarketDataManager so historical data is
loaded once and shared across the application.
"""

from datetime import datetime

from services.market.market_data_manager import (
    market_data_manager,
)

from services.indicator_engine import (
    calculate_indicators,
)
from services.analysis.smart_money_pipeline import (
    analyze as analyze_smart_money_pipeline,
)
from services.market.option_market import (
    OptionMarket,
)
from utils.debug import debug_print

EXCHANGE = "NSE"
SYMBOL_TOKEN = "99926000"
UNDERLYING = "NIFTY"


def get_market_snapshot():

    option_market = OptionMarket()

    # -----------------------------------------------------
    # Centralized Market Data
    # -----------------------------------------------------

    df = market_data_manager.get_timeframe(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        timeframe="5m",
    )

    if df.empty:
        raise ValueError(
            "No market data received."
        )

    df.columns = [
        c.lower()
        for c in df.columns
    ]

    data, indicators = calculate_indicators(
        df
    )
    smart_money = analyze_smart_money_pipeline(
    data
    )
    

    debug_print(
        "SMART MONEY:",
        {
            "BOS": smart_money.get("bos"),
            "CHOCH": smart_money.get("choch"),
            "Bullish OB": (
                smart_money.get("order_blocks", {}).get("bullish")
                is not None
            ),
            "Bearish OB": (
                smart_money.get("order_blocks", {}).get("bearish")
                is not None
            ),
            "Bullish FVG": (
                smart_money.get("fair_value_gaps", {}).get("bullish")
                is not None
            ),
            "Bearish FVG": (
                smart_money.get("fair_value_gaps", {}).get("bearish")
                is not None
            ),
        },
    )
    latest = data.iloc[-1]

    ltp = float(
        latest["close"]
    )

    now = datetime.now()

    market_open = (
        now.weekday() < 5
        and (
            now.hour > 9
            or (
                now.hour == 9
                and now.minute >= 15
            )
        )
        and (
            now.hour < 15
            or (
                now.hour == 15
                and now.minute <= 30
            )
        )
    )

    try:

        option_analysis = option_market.analyze(
            UNDERLYING,
            ltp,
        )

    except Exception as e:

        import traceback

        traceback.print_exc()

        option_analysis = {

            "Status": "Error",

            "Error": str(e),

        }

    return {

        "symbol": UNDERLYING,

        "history": data,

        "ltp": ltp,

        "open": float(
            latest["open"]
        ),

        "high": float(
            latest["high"]
        ),

        "low": float(
            latest["low"]
        ),

        "close": float(
            latest["close"]
        ),

        "volume": float(
            latest["volume"]
        ),

        "timestamp": str(
            latest.name
        ),

        "refresh_time": now.strftime(
            "%H:%M:%S"
        ),

        "market_status": (
            "OPEN"
            if market_open
            else "CLOSED"
        ),

        "indicators": indicators,

        "option_analysis": option_analysis,
        "smart_money": smart_money,
    }