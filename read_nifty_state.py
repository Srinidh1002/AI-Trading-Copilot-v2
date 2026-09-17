import json
with open("data/paper_trades/nifty_experimental.json", encoding="utf-8") as f:
    d = json.load(f)
print(f"Keys: {list(d.keys())}")
print(f"current_session: {d.get('current_session')}")
print(f"total_trades: {d.get('total_trades')}")
print(f"sessions_completed_today: {d.get('sessions_completed_today')}")
print(f"total_pnl: {d.get('total_pnl')}")
sh = d.get("session_history", [])
print(f"session_history length: {len(sh)}")
for i, s in enumerate(sh[-6:]):
    print(f"  [{i}] {s}")
