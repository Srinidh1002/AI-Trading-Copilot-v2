"""
Market Snapshot

Creates a complete institutional market snapshot that is shared
across every engine.
"""

from dataclasses import asdict
from datetime import datetime

from services.core.snapshot_schema import Snapshot
from services.market.market_data_manager import (
    market_data_manager,
)
from services.market.live_multi_timeframe_engine import (
    LiveMultiTimeframeEngine,
)
from services.core.constants import (
    EXCHANGE,
    SYMBOL_TOKEN,
    DEFAULT_TIMEFRAME,
)
from services.indicators.indicator_engine import (
    calculate_indicators,
)
from services.market.option_market import OptionMarket
from services.analysis.smart_money_pipeline import (
    analyze as analyze_smart_money_pipeline,
)

def get_market_snapshot():
    print(">>> MARKET SNAPSHOT FUNCTION CALLED <<<")
    mtf_engine = LiveMultiTimeframeEngine()

    option_engine = OptionMarket()

    df = market_data_manager.get_timeframe(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        timeframe=DEFAULT_TIMEFRAME,
    )

    latest = df.iloc[-1]

    now = datetime.now()

    market_open = (
        now.weekday() < 5
        and (
            (now.hour > 9)
            or (
                now.hour == 9
                and now.minute >= 15
            )
        )
        and (
            (now.hour < 15)
            or (
                now.hour == 15
                and now.minute <= 30
            )
        )
    )

    indicators = calculate_indicators(df)
    smart_money = analyze_smart_money_pipeline(
    df
    )
    try:

        multi_timeframe = mtf_engine.analyze(
            EXCHANGE,
            SYMBOL_TOKEN,
        )

    except Exception as e:

        multi_timeframe = {

            "Bias": "Unknown",

            "Confidence": 0,

            "BullScore": 0,

            "BearScore": 0,

            "Confirmations": [],

            "Error": str(e),

        }

    try:

        option_analysis = option_engine.analyze(
            spot=float(latest["close"]),
        )

    except Exception as e:

        option_analysis = {

            "Status": "Failed",

            "Error": str(e),

        }

    snapshot = Snapshot(

        history=df,

        ltp=float(latest["close"]),

        open=float(latest["open"]),

        high=float(latest["high"]),

        low=float(latest["low"]),

        close=float(latest["close"]),

        volume=int(latest["volume"]),

        candle_time=str(latest["timestamp"]),

        market_status="OPEN"
        if market_open
        else "CLOSED",

        refresh_time=now.strftime("%H:%M:%S"),

        indicators=indicators,

        analysis={

            "multi_timeframe": multi_timeframe,

            "smart_money": smart_money,
        },

        decision={},

        risk={},

    )

    result = asdict(snapshot)
    result.update(smart_money)
    print(
        "SMART MONEY:",
        smart_money,
    )
    result["option_analysis"] = option_analysis

    result["multi_timeframe"] = multi_timeframe

    return result