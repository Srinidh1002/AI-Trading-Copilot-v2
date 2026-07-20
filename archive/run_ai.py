from services.ai.live_trading_ai import LiveTradingAI

ai = LiveTradingAI(
    symbol="NIFTY",
    spot=24346.7,
    levels=10,
    interval=30,
)

ai.start()