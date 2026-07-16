"""
Central Trading Configuration

Every live runner imports these values.

Never hardcode capital, risk or underlying
inside strategy files.
"""

CAPITAL = 10_000

RISK_PERCENT = 1.0

UNDERLYING = "NIFTY"

ENABLE_PAPER_TRADING = True

PERSIST_PAPER_TRADES = True

BREAKOUT_BUFFER_PERCENT = 0.0

MAXIMUM_CAPITAL_USAGE_PERCENT = 100.0