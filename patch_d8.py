"""D8 — Fix same_direction_stops self-comparison in close_position.

Before: `last_exit_direction` is set from THIS trade, then compared against
        THIS trade's direction (always equal). Every STOP_LOSS incremented.
After:  Prior direction is captured before overwrite. Streak only increments
        on genuine consecutive same-direction stops. First stop starts at 1.
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D8_same_direction_fix" in src:
    print("D8 already applied")
    raise SystemExit(0)

old = '''            self.last_exit_time = datetime.now()
            self.last_exit_direction = trade.get('type', 'UNKNOWN')
            self.daily_trade_count += 1
            _net = trade.get('net_pnl', 0) or 0
            self.daily_realized_loss += _net
            
            if reason == 'STOP_LOSS' and trade.get('type') == self.last_exit_direction:
                self.same_direction_stops += 1
            else:
                self.same_direction_stops = 0'''

new = '''            self.last_exit_time = datetime.now()
            # D8_same_direction_fix — capture prior direction BEFORE overwrite
            _prev_exit_direction = self.last_exit_direction
            self.last_exit_direction = trade.get('type', 'UNKNOWN')
            self.daily_trade_count += 1
            _net = trade.get('net_pnl', 0) or 0
            self.daily_realized_loss += _net
            
            if reason == 'STOP_LOSS':
                if _prev_exit_direction is not None and trade.get('type') == _prev_exit_direction:
                    self.same_direction_stops += 1
                else:
                    self.same_direction_stops = 1   # new direction streak starts at 1
            else:
                self.same_direction_stops = 0'''

if old not in src:
    raise SystemExit("D8 anchor not found — abort")

src = src.replace(old, new, 1)
with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D8: same_direction_stops logic fixed")
