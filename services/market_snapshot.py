"""
Market Snapshot Service V3.11

Uses the centralized MarketDataManager and Refresh Manager.
"""

from datetime import datetime
from services.refresh import snapshot_cache
from services.market.market_data_manager import (
    market_data_manager,
)
from services.utils import safe_execute
from services.indicator_engine import (
    calculate_indicators,
)

from services.analysis.smart_money_pipeline import (
    analyze as analyze_smart_money_pipeline,
)

from services.market.option_market import (
    OptionMarket,
)

from services.market.live_ltp import (
    live_ltp,
)

from services.refresh.refresh_manager import (
    refresh_manager,
)

from services.refresh.refresh_intervals import (
    OPTION_CHAIN,
)
from services.performance import performance_monitor
from utils.debug import debug_print

EXCHANGE = "NSE"
SYMBOL_TOKEN = "99926000"
UNDERLYING = "NIFTY"

_option_market = OptionMarket()

_cached_option_analysis = {
    "Status": "Loading"
}


def _build_market_snapshot():

    performance_monitor.start("market_snapshot")
    global _cached_option_analysis

    df = market_data_manager.get_timeframe(
        exchange=EXCHANGE,
        symboltoken=SYMBOL_TOKEN,
        timeframe="5m",
        force_refresh=True,
    )

    if df.empty:
        raise ValueError("No market data received.")

    df.columns = [c.lower() for c in df.columns]

    result = safe_execute(
        calculate_indicators,
        default=(df, {}),
        df=df,
    )

    data, indicators = result

    smart_money = safe_execute(
        analyze_smart_money_pipeline,
        default={},
        data=data,
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

    try:
        ltp = live_ltp.get_ltp(
            exchange=EXCHANGE,
            tradingsymbol=UNDERLYING,
            symboltoken=SYMBOL_TOKEN,
        )
    except Exception:
        ltp = float(latest["close"])

    if refresh_manager.should_refresh(
        "option_chain",
        OPTION_CHAIN,
    ):
        try:
            _cached_option_analysis = _option_market.analyze(
                UNDERLYING,
                ltp,
            )
        except Exception:
            pass

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
    performance_monitor.stop("market_snapshot")
    return {

        "symbol": UNDERLYING,

        "history": data,

        "ltp": ltp,

        "open": float(latest["open"]),

        "high": float(latest["high"]),

        "low": float(latest["low"]),

        "close": float(latest["close"]),

        "volume": float(latest["volume"]),

        "timestamp": str(latest.name),

        "refresh_time": now.strftime("%H:%M:%S"),

        "market_status": (
            "OPEN"
            if market_open
            else "CLOSED"
        ),

        "indicators": indicators,

        "option_analysis": _cached_option_analysis,

        "smart_money": smart_money,
    }
def get_market_snapshot():

    return snapshot_cache.get(
        _build_market_snapshot
    )