import hashlib
files = [
    "data/paper_trades/mcx_crudeoilm_experimental.json",
    "data/paper_trades/mcx_goldm_experimental.json",
    "data/paper_trades/mcx_natgasmini_experimental.json",
    "data/paper_trades/mcx_crudeoilm_decisions.jsonl",
    "data/paper_trades/mcx_crudeoilm_predictions.jsonl",
    "data/paper_trades/mcx_crudeoilm_outcomes.jsonl",
]
for p in files:
    try:
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
        print(f"{h}  {p}")
    except FileNotFoundError:
        print(f"{'(missing)':16}  {p}")
