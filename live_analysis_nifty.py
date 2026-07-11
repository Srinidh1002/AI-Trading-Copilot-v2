"""
First complete read-only live NIFTY analysis.

No orders are placed.
"""

from pprint import pprint

from services.live_analysis_pipeline import (
    LiveAnalysisPipeline,
)


EXCHANGE = "NSE"
NIFTY_TOKEN = "99926000"


print("\n================================")
print("AI TRADING COPILOT")
print("LIVE NIFTY ANALYSIS")
print("================================\n")

print("Fetching and analysing live market data...\n")

pipeline = LiveAnalysisPipeline()

result = pipeline.analyse(
    exchange=EXCHANGE,
    symboltoken=NIFTY_TOKEN,
)


print("\n--- TECHNICAL ANALYSIS ---")
pprint(result["technical"])


print("\n--- MULTI-TIMEFRAME ANALYSIS ---")
pprint(result["timeframe"])


print("\n--- MARKET REGIME ---")
pprint(result["regime"])


print("\n--- CANDLESTICK PATTERNS ---")
pprint(result["candlestick"])


print("\n--- CHART PATTERNS ---")
pprint(result["chart"])


print("\n--- STRATEGY DECISION ---")
pprint(result["strategy"])


print("\n================================")
print("FINAL MARKET VIEW")
print("================================")

strategy = result["strategy"]

print(
    "Decision:",
    strategy.get("decision")
)

print(
    "Strategy:",
    strategy.get("strategy")
)

print(
    "Direction:",
    strategy.get("direction")
)

print(
    "Confidence:",
    f"{strategy.get('confidence', 0)}%"
)

print("\nConfirmations:")

for reason in strategy.get(
    "confirmations",
    [],
):
    print("✓", reason)


print("\nRisk Flags:")

risk_flags = strategy.get(
    "risk_flags",
    [],
)

if risk_flags:
    for risk in risk_flags:
        print("⚠", risk)
else:
    print("None")


print("\nREAD-ONLY ANALYSIS COMPLETE")
print("NO ORDER WAS PLACED")