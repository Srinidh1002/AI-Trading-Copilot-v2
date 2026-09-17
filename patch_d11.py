"""D11 - Fetch live FULL quote at entry so paper fill gets real bid/ask.

Before: entry read trade['bid'] and trade['ask'] from the chain ranking.
        Both are 0 because the chain engine is LTP-only.
        Result: compute_paper_fill returns NO_VALID_ASK, every entry refused.

After:  one _fetch_option_quote_full call before fill computation.
        Uses the same helper D7/D9 already added for the monitor loop.
        Same rate-limit budget. No new API surface.
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D11_entry_full_quote" in src:
    print("D11 already applied")
    raise SystemExit(0)

old = '''        # ===== PHASE F: Realistic paper fill =====
        _bid = float(trade.get("bid", 0) or 0)
        _ask = float(trade.get("ask", 0) or 0)
        _ltp = float(trade.get("entry", 0))
        _fill, _fill_status = self.capital_engine.compute_paper_fill(_bid, _ask, _ltp, direction="BUY")'''

new = '''        # ===== PHASE F: Realistic paper fill =====
        # D11_entry_full_quote - fetch live bid/ask (chain engine is LTP-only)
        _entry_quote = self._fetch_option_quote_full(trade["symbol"], trade["token"])
        _bid = float(_entry_quote.get("bid") or 0)
        _ask = float(_entry_quote.get("ask") or 0)
        _ltp = float(_entry_quote.get("ltp") or trade.get("entry") or 0)
        if _bid <= 0 or _ask <= 0 or _ask <= _bid:
            print(f"  ENTRY_FULL_QUOTE_INCOMPLETE: bid={_bid} ask={_ask} ltp={_ltp}")
            print(f"  Refusing trade - entry requires live full depth")
            self.decision_state = 'BLOCKED'
            return None
        _fill, _fill_status = self.capital_engine.compute_paper_fill(_bid, _ask, _ltp, direction="BUY")'''

if old not in src:
    raise SystemExit("D11 anchor not found")
src = src.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D11: entry now fetches live FULL quote for bid/ask")
