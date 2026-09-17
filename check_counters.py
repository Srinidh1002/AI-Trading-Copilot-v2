import json
for p in ['crudeoilm', 'goldm', 'natgasmini']:
    f = f"data/paper_trades/mcx_{p}_experimental.json"
    st = json.load(open(f, encoding="utf-8"))
    print(f"{p}: trades={st['total_trades']} t1={st.get('t1_hit_wins',0)} sl={st.get('sl_losses',0)}")
