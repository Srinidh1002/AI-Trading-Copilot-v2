"""D2 — Add explicit PAPER-mode safety flags and hard refuse if misconfigured.

Before: safety was structural only (no order API imported anywhere in
        the NIFTY/SENSEX path). This is strong but not visible in code.
After:  three explicit class-level flags set in __init__, asserted at the
        top of every session. Any future code that flips them will crash
        loudly, not silently trade.
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D2_safety_flags" in src:
    print("D2 already applied")
    raise SystemExit(0)

# 1. Add three flags in __init__, right after STOP_LOSS_PERCENT
old_init = '''        self.T1_PERCENT = 15
        self.T2_PERCENT = 30
        self.T3_PERCENT = 50
        self.STOP_LOSS_PERCENT = 5'''
new_init = '''        self.T1_PERCENT = 15
        self.T2_PERCENT = 30
        self.T3_PERCENT = 50
        self.STOP_LOSS_PERCENT = 5
        
        # D2_safety_flags — explicit PAPER-only contract
        self.EXECUTION_MODE = "PAPER"
        self.BROKER_SUBMISSION = False
        self.LIVE_EXECUTION = False'''

if old_init not in src:
    raise SystemExit("D2 init anchor not found")
src = src.replace(old_init, new_init, 1)

# 2. Hard assertion at top of run_single_session
old_fn = '''    def run_single_session(self):
        if not self.is_running:
            return None'''
new_fn = '''    def run_single_session(self):
        # D2_safety_flags — hard refuse if any mode flag is misconfigured
        assert self.EXECUTION_MODE == "PAPER", "EXECUTION_MODE must be PAPER"
        assert self.BROKER_SUBMISSION is False, "BROKER_SUBMISSION must be False"
        assert self.LIVE_EXECUTION is False, "LIVE_EXECUTION must be False"
        
        if not self.is_running:
            return None'''

if old_fn not in src:
    raise SystemExit("D2 run_single_session anchor not found")
src = src.replace(old_fn, new_fn, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D2: safety flags added + runtime assertion")
