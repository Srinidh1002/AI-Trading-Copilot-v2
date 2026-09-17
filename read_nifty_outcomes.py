import json, os
# Check outcomes ledger
p = "data/paper_trades/nifty_outcomes.jsonl"
if os.path.exists(p):
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()
    print(f"nifty_outcomes.jsonl has {len(lines)} records")
    for line in lines[-5:]:
        try:
            d = json.loads(line)
            print(f"  {d.get('trade_id','?')}: entry={d.get('entry')} exit={d.get('exit')} net_pnl={d.get('net_pnl')} reason={d.get('exit_reason')} cert_eligible={d.get('certification_eligible')}")
        except Exception as e:
            print(f"  parse err: {e}")
else:
    print(f"{p} does not exist")
