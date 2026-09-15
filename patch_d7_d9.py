"""D7 + D9 — Executable-bid trail + Design B lock-in (Reading B).

D7: monitor loop fetches FULL quote (LTP + depth) once per cycle;
    all exits use bid - slippage; pnl/pnl_pct recomputed from actual exit.

D9 (Design B / Reading B):
    T1 (+15% LTP) activates trail. Trail = max(entry*1.10, peak_bid*0.95).
    Floor +10% is a hard rule. T3 (+50%) and SL (-5%) still exit hard.
    T1/T2 parallel close branches removed.
"""
import re
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D7_D9_design_b" in src:
    print("D7+D9 already applied")
    raise SystemExit(0)

# ============ 1. Insert helper methods ============
anchor_close = "    def run_daily_sessions(self):"
helpers = '''    # ===== D7_D9_design_b — full quote + bid-based exits =====
    def _fetch_option_quote_full(self, symbol, token):
        """One REST call: LTP + best bid + best ask. None for missing fields."""
        try:
            self.rate_limiter.wait_if_needed("ltp_data")
            resp = self.obj.getMarketData(
                "FULL", {self.option_exchange: [str(token)]}
            )
            if not resp or not resp.get("data"):
                return {"ltp": None, "bid": None, "ask": None}
            rows = resp["data"].get("fetched") or []
            row = None
            for r in rows:
                if str(r.get("symbolToken")) == str(token):
                    row = r
                    break
            if row is None:
                return {"ltp": None, "bid": None, "ask": None}
            ltp = row.get("ltp")
            try:
                ltp = float(ltp) if ltp is not None else None
            except (TypeError, ValueError):
                ltp = None
            depth = row.get("depth") or {}
            bids = depth.get("buy") or []
            asks = depth.get("sell") or []
            bid = None
            ask = None
            if bids and bids[0].get("price"):
                try: bid = float(bids[0]["price"])
                except (TypeError, ValueError): bid = None
            if asks and asks[0].get("price"):
                try: ask = float(asks[0]["price"])
                except (TypeError, ValueError): ask = None
            return {"ltp": ltp, "bid": bid, "ask": ask}
        except Exception as e:
            print(f"  [FULL_QUOTE] err: {str(e)[:60]}")
            return {"ltp": None, "bid": None, "ask": None}

    def _exit_price_from_bid(self, bid):
        """Exit fill = bid minus adverse slippage (same % as entry)."""
        if bid is None or bid <= 0:
            return None
        slip = bid * (self.capital_engine.slippage_pct / 100.0)
        return round(bid - slip, 2)

    def _bid_based_exit(self, entry, exit_bid, fallback_ltp, lot_size):
        """(exit_px, pnl, pnl_pct) using executable bid. Falls back to LTP with warning."""
        exit_px = self._exit_price_from_bid(exit_bid)
        if exit_px is None:
            exit_px = fallback_ltp
            print(f"  [D7] WARN: no bid available, using LTP {exit_px:.2f} as exit")
        pnl = (exit_px - entry) * lot_size
        pnl_pct = ((exit_px - entry) / entry) * 100 if entry else 0.0
        return exit_px, pnl, pnl_pct
    # ===== end D7_D9 helpers =====

    def run_daily_sessions(self):'''

if anchor_close not in src:
    raise SystemExit("D7+D9: run_daily_sessions anchor not found")
src = src.replace(anchor_close, helpers, 1)

# ============ 2. peak_bid field at trade init ============
anchor_init = """        active_trade['t1_hit'] = False
        active_trade['t2_hit'] = False
        active_trade['peak_price'] = entry
        active_trade['trail_stop'] = None
        active_trade['entry_spot'] = spot"""
new_init = """        active_trade['t1_hit'] = False
        active_trade['t2_hit'] = False
        active_trade['peak_price'] = entry
        active_trade['peak_bid'] = None  # D7_D9_design_b
        active_trade['trail_stop'] = None
        active_trade['entry_spot'] = spot"""
if anchor_init not in src:
    raise SystemExit("D7+D9: init anchor not found")
src = src.replace(anchor_init, new_init, 1)

# ============ 3. Replace data-fetch block ============
old_fetch = """            try:
                current_price = 0
                # Try WebSocket first
                if self.ws_feed and self.ws_feed.is_healthy():
                    ws_tick = self.ws_feed.get_latest(trade['token'])
                    if ws_tick and ws_tick.get("ltp", 0) > 0:
                        current_price = ws_tick["ltp"]
                
                # Fallback to REST if WS stale
                if current_price <= 0:
                    self.rate_limiter.wait_if_needed("ltp_data")
                    ltp_data = self.obj.ltpData(self.option_exchange, trade['symbol'], trade['token'])
                    if ltp_data and ltp_data.get('data'):
                        current_price = float(ltp_data['data'].get('ltp', 0))
                
                if current_price > 0:"""
new_fetch = """            try:
                # D7_D9_design_b — one full-quote call per cycle: LTP + bid + ask
                quote = self._fetch_option_quote_full(trade['symbol'], trade['token'])
                current_ltp = quote.get('ltp') or 0
                current_bid = quote.get('bid')  # may be None
                current_price = current_ltp  # LTP drives pnl/threshold decisions
                
                # Track peak executable bid
                if current_bid is not None and current_bid > 0:
                    if active_trade.get('peak_bid') is None or current_bid > active_trade['peak_bid']:
                        active_trade['peak_bid'] = current_bid
                
                if current_price > 0:"""
if old_fetch not in src:
    raise SystemExit("D7+D9: fetch anchor not found")
src = src.replace(old_fetch, new_fetch, 1)

# ============ 4. Replace target_policy block with inline Design B trail ============
old_policy = """                        # ===== PHASE F: MFE/MAE + Target policy =====
                        try:
                            self.mfe_mae.update(trade_id, current_price)
                            if 'peak_price' not in active_trade or current_price > active_trade['peak_price']:
                                active_trade['peak_price'] = current_price
                            target_state = {
                                'entry_price': entry,
                                'current_price': current_price,
                                'peak_price': active_trade.get('peak_price', current_price),
                                'trail_stop': active_trade.get('trail_stop'),
                                't1_hit': active_trade.get('t1_hit', False),
                                't2_hit': active_trade.get('t2_hit', False),
                            }
                            action, reason, new_trail, updates = self.target_policy.evaluate(target_state)
                            for k, v in updates.items():
                                active_trade[k] = v
                            if new_trail is not None:
                                active_trade['trail_stop'] = new_trail
                            if action == 'EXIT_T3':
                                print(f'  T3 REACHED at {current_price:.2f}')
                                self.close_position(trade_id, current_price, 'T3_50%', pnl, pnl_pct)
                                self.t3_hits += 1
                                break
                            if active_trade.get('trail_stop') and current_price <= active_trade['trail_stop']:
                                print(f'  TRAIL STOP HIT at {current_price:.2f}')
                                self.close_position(trade_id, current_price, 'TRAIL_STOP', pnl, pnl_pct)
                                break
                        except Exception as _e:
                            print(f'[F] policy error: {str(_e)[:60]}')"""
new_policy = """                        # ===== D7_D9_design_b — inline Design B trail (Reading B) =====
                        # T1 (+15% LTP) activates trail, does NOT exit.
                        # Trail = max(entry * 1.10, peak_bid * 0.95). Never below +10%.
                        # T3 (+50%) and SL (-5%) still exit hard.
                        try:
                            self.mfe_mae.update(trade_id, current_price)
                            if 'peak_price' not in active_trade or current_price > active_trade['peak_price']:
                                active_trade['peak_price'] = current_price
                            
                            _floor = entry * 1.10  # +10% premium lock
                            
                            # Activation: first time LTP pnl_pct crosses T1
                            if not active_trade.get('t1_hit') and pnl_pct >= self.T1_PERCENT:
                                active_trade['t1_hit'] = True
                                _pb = active_trade.get('peak_bid')
                                _init_stop = _floor
                                if _pb is not None:
                                    _init_stop = max(_floor, _pb * 0.95)
                                active_trade['trail_stop'] = _init_stop
                                print(f'  [T1] trail ACTIVE floor={_floor:.2f} stop={_init_stop:.2f}')
                            
                            # Update: after T1, chase peak_bid with 5% step, floored at +10%
                            if active_trade.get('t1_hit'):
                                _pb = active_trade.get('peak_bid')
                                if _pb is not None:
                                    _cand = max(_floor, _pb * 0.95)
                                    if _cand > (active_trade.get('trail_stop') or 0):
                                        active_trade['trail_stop'] = _cand
                            
                            # Exit: current bid at or below trail stop
                            if active_trade.get('t1_hit'):
                                _stop = active_trade.get('trail_stop')
                                if _stop is not None and current_bid is not None:
                                    if current_bid <= _stop:
                                        _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                                            entry, current_bid, current_price, self.lot_size)
                                        print(f'  TRAIL STOP HIT: bid={current_bid:.2f} stop={_stop:.2f} exit={_exit_px:.2f}')
                                        self.close_position(trade_id, _exit_px, 'TRAIL_STOP', _pnl, _pnl_pct)
                                        break
                        except Exception as _e:
                            print(f'[F] policy error: {str(_e)[:60]}')"""
if old_policy not in src:
    raise SystemExit("D7+D9: policy anchor not found")
src = src.replace(old_policy, new_policy, 1)

# ============ 5. Parallel chain: remove T1/T2, bid-based T3/SL ============
old_chain = """                        if pnl_pct >= self.T3_PERCENT:
                            self.close_position(trade_id, current_price, 'T3_50%', pnl, pnl_pct)
                            self.t3_hits += 1
                            break
                        elif pnl_pct >= self.T2_PERCENT:
                            self.close_position(trade_id, current_price, 'T2_30%', pnl, pnl_pct)
                            self.t2_hits += 1
                            break
                        elif pnl_pct >= self.T1_PERCENT:
                            self.close_position(trade_id, current_price, 'T1_15%', pnl, pnl_pct)
                            self.t1_hits += 1
                            break
                        elif pnl_pct <= -self.STOP_LOSS_PERCENT:
                            self.close_position(trade_id, current_price, 'STOP_LOSS', pnl, pnl_pct)
                            self.stop_losses += 1
                            break"""
new_chain = """                        # D7_D9_design_b — T1/T2 no longer exit here (T1 activates trail above)
                        if pnl_pct >= self.T3_PERCENT:
                            _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                                entry, current_bid, current_price, self.lot_size)
                            print(f'  T3 REACHED: ltp_pct={pnl_pct:.2f}% exit={_exit_px:.2f}')
                            self.close_position(trade_id, _exit_px, 'T3_50%', _pnl, _pnl_pct)
                            self.t3_hits += 1
                            break
                        elif pnl_pct <= -self.STOP_LOSS_PERCENT:
                            _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                                entry, current_bid, current_price, self.lot_size)
                            self.close_position(trade_id, _exit_px, 'STOP_LOSS', _pnl, _pnl_pct)
                            self.stop_losses += 1
                            break"""
if old_chain not in src:
    raise SystemExit("D7+D9: parallel chain anchor not found")
src = src.replace(old_chain, new_chain, 1)

# ============ 6. Spot invalidation — bid-based (regex to skip emoji) ============
new_spot = ("_exit_px, _pnl, _pnl_pct = self._bid_based_exit("
            "entry, current_bid, current_price, self.lot_size)\n"
            "                                        self.close_position(trade_id, _exit_px, "
            "'SPOT_INVALIDATED', _pnl, _pnl_pct)")
src, n = re.subn(
    r"self\.close_position\(trade_id, current_price, 'SPOT_INVALIDATED', pnl, pnl_pct\)",
    new_spot, src
)
if n != 2:
    raise SystemExit(f"D7+D9: SPOT_INVALIDATED replacements = {n}, expected 2")

# ============ 7. Session-close — bid-based ============
old_sess = """        if trade_id in self.active_trades:
            try:
                ltp_data = self.obj.ltpData(self.option_exchange, trade['symbol'], trade['token'])
                if ltp_data and ltp_data.get('data'):
                    current_price = float(ltp_data['data'].get('ltp', 0))
                    if trade['signal'] == 'BUY':
                        pnl = (current_price - entry) * self.lot_size
                        pnl_pct = ((current_price - entry) / entry) * 100
                    else:
                        pnl = (entry - current_price) * self.lot_size
                        pnl_pct = ((entry - current_price) / entry) * 100
                    
                    self.close_position(trade_id, current_price, 'MARKET_CLOSE_3:28PM', pnl, pnl_pct)
                    self.market_close_exits += 1
            except:
                pass"""
new_sess = """        if trade_id in self.active_trades:
            try:
                # D7_D9_design_b — session-close uses bid-based exit too
                _quote = self._fetch_option_quote_full(trade['symbol'], trade['token'])
                _ltp = _quote.get('ltp') or 0
                _bid = _quote.get('bid')
                if _ltp > 0:
                    _exit_px, _pnl, _pnl_pct = self._bid_based_exit(
                        entry, _bid, _ltp, self.lot_size)
                    self.close_position(trade_id, _exit_px, 'MARKET_CLOSE_3:28PM', _pnl, _pnl_pct)
                    self.market_close_exits += 1
            except Exception as _e:
                print(f"  [session-close] err: {str(_e)[:60]}")"""
if old_sess not in src:
    raise SystemExit("D7+D9: session-close anchor not found")
src = src.replace(old_sess, new_sess, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D7+D9: Design B trail + bid-based exits applied")
