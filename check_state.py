import json, os
for m in ("nifty", "sensex"):
    p = f"data/paper_trades/{m}_state.json"
    if os.path.exists(p):
        d = json.load(open(p, encoding="utf-8"))
        print(f"{m.upper()}: current_session={d.get('current_session')} total_trades={d.get('total_trades')}")
    else:
        print(f"{m.upper()}: no state file")
