"""N1B - 14-fix re-verification. Read-only greps."""
import os, re

BOT = "src/target_focused_bot.py"
with open(BOT, encoding="utf-8") as f:
    bot = f.read()
bot_lines = bot.splitlines()

# Also load a few supporting files
SUPPORT = {}
for fn in ("market_phase.py", "capital_engine.py", "quote_freshness.py",
           "websocket_feed.py", "oi_analyzer.py", "option_chain_engine.py",
           "strike_ranker.py", "contract_metadata.py"):
    p = os.path.join("src", fn)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            SUPPORT[fn] = f.read()

CHECKS = [
    # (id, label, file, pattern, expected_hit)
    ("F01", "batched marketData FULL", BOT, r"getMarketData\(", True),
    ("F02", "depth parsing present",     BOT, r"depth", True),
    ("F03", "strike_ranker -> select_trade", BOT, r"StrikeRanker|strike_ranker|rank_strikes", True),
    ("F04", "WebSocket list-payload handling", "websocket_feed.py", r"isinstance\(data,\s*list\)|isinstance\(.*,\s*list\)", True),
    ("F05", "quote freshness",           "quote_freshness.py", r"QuoteFreshnessTracker|freshness", True),
    ("F06", "health string handling",    BOT, r"health_str|WS_STATUS|HEALTHY|STALE_WS", True),
    ("F07", "ZERO_OI handling",          "oi_analyzer.py", r"ZERO_OI|zero_oi|oi\s*==\s*0", True),
    ("F08", "continuous runtime / max_attempts", BOT, r"max_attempts|is_running|while\s+self\.is_running", True),
    ("F09", "candle cache",              None, None, None),  # search everywhere
    ("F10", "failure TTL",               None, None, None),
    ("F11", "RULE9 error handling",      None, None, None),
    ("F12", "P&L fallback",              BOT, r"net_pnl\s+if.*else\s+pnl|pnl\s+if.*else", True),
    ("F13", "RULE14 / doraise",          None, None, None),
    ("F14", "tick-aware fills (new D6)", "capital_engine.py", r"_round_to_tick|OPTION_TICK", True),
]

def grep_text(text, pattern):
    try:
        return [m.start() for m in re.finditer(pattern, text, re.IGNORECASE)]
    except Exception:
        return []

print("=" * 90)
print("N1B - 14-FIX RE-VERIFICATION")
print("=" * 90)
for cid, label, fname, pat, expect in CHECKS:
    if pat is None:
        # search everywhere
        hits_total = 0
        where = []
        for name, text in SUPPORT.items():
            h = grep_text(text, "candle_cache|cache.*candle|CandleBuilder|_candles" if cid == "F09"
                          else "failure_ttl|failure-ttl|TTL|ttl" if cid == "F10"
                          else "RULE9|rule_9|specific exception" if cid == "F11"
                          else "doraise|py_compile" if cid == "F13"
                          else "")
            if h:
                hits_total += len(h)
                where.append(f"{name}({len(h)})")
        bh = 0
        if cid == "F09": bh = len(grep_text(bot, "candle_cache|CandleBuilder|_candles"))
        elif cid == "F10": bh = len(grep_text(bot, "failure_ttl|TTL|ttl"))
        elif cid == "F11": bh = len(grep_text(bot, "RULE9|rule_9"))
        elif cid == "F13": bh = len(grep_text(bot, "doraise"))
        print(f"  {cid} {label:<40} hits={hits_total+bh}  where={','.join(where) if where else 'bot'}")
        continue

    if fname == BOT:
        text = bot
    elif fname in SUPPORT:
        text = SUPPORT[fname]
    else:
        print(f"  {cid} {label:<40} FILE NOT FOUND: {fname}")
        continue
    hits = grep_text(text, pat)
    status = "VERIFIED_CURRENT" if (bool(hits) == expect) else "REGRESSED"
    print(f"  {cid} {label:<40} {status:<20} hits={len(hits)}")
