from services.core import get_market_snapshot
from services.decision import make_decision
from services.ai.ai_engine import generate_ai_analysis
from services.analysis import analyze_multi_timeframe
from services.analysis import analyze_market_structure

snapshot = get_market_snapshot()
print(snapshot["history"].columns.tolist())
mtf = analyze_multi_timeframe(snapshot)
structure = analyze_market_structure(snapshot)
decision = make_decision(snapshot)
ai = generate_ai_analysis(snapshot, decision)

print("\nSnapshot Loaded")
print("LTP:", snapshot["ltp"])
print("\nMulti Timeframe")
print(mtf)
print("\nMarket Structure")
print(structure)
print("\nDecision Engine Loaded")
print("\nSwing Detection")
print(snapshot["swings"])

print("\nBreak Of Structure")
print(snapshot["bos"])

print("\nCHoCH")
print(snapshot["choch"])

print("\nLiquidity")
print(snapshot["liquidity"])
print("\nKeys:")
print(decision.keys())
print("\nOrder Blocks")
print(snapshot["order_blocks"])

print("\nFair Value Gaps")
print(snapshot["fair_value_gaps"])

print("\nSupply Demand")
print(snapshot["supply_demand"])
print("\nReasons:")
print(decision.get("reasons"))

print("\nSummary:")
print(decision.get("summary"))

print("\nFull Decision:")
print(decision)

print("\nAI Analysis\n")
print(ai["analysis"])