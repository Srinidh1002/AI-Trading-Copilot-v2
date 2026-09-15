import os, re

patterns = [
    (r"placeOrder|modifyOrder|cancelOrder", "LIVE_ORDER_API"),
    (r"BROKER_SUBMISSION", "BROKER_FLAG"),
    (r"LIVE_EXECUTION", "LIVE_FLAG"),
    (r"EXECUTION_MODE", "EXEC_MODE"),
    (r"certification_eligible|cert_eligible", "CERT_ELIGIBLE"),
    (r"current_session\b", "SESSION_COUNTER"),
    (r"session_history", "SESSION_HISTORY"),
    (r"MAX_LOTS|max_lots|capital_engine|CapitalEngine", "CAPITAL"),
    (r"MARKET_OPEN|FINAL_EXIT|is_market_open", "SESSION_TIME"),
    (r"WebSocket|websocket_feed|SmartWebSocket", "WS"),
    (r"getMarketData|option_chain|fetch_chain", "CHAIN_FETCH"),
    (r"T1|T2|T3|target_hit|hit_target", "TARGETS"),
    (r"stop_loss|SL|invalidate", "STOPS"),
]

for path in ("src/target_focused_bot.py", "run_nifty.py", "run_sensex.py"):
    print(f"\n{'=' * 90}")
    print(f"{path}")
    print("=" * 90)
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for label, pat in [(l, p) for p, l in patterns]:
        hits = []
        for i, l in enumerate(lines, 1):
            if re.search(pat, l):
                hits.append((i, l.rstrip()[:110]))
        if hits:
            print(f"\n  [{label}] — {len(hits)} hits")
            for i, l in hits[:10]:
                print(f"    {i:5d}: {l}")
