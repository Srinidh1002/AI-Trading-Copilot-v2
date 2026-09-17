"""D14 - guard signal.signal() with try/except for thread-safety.

Before: signal.signal(SIGINT, handler) at init raises ValueError when the
        bot is instantiated inside a worker thread.
After:  wrapped in try/except ValueError - main-thread runs unchanged,
        threaded runs skip handler registration without crashing.

Zero impact on production runners (they run in main thread).
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D14_thread_safe_signal" in src:
    print("D14 already applied")
    raise SystemExit(0)

old = "        signal.signal(signal.SIGINT, self.signal_handler)"
new = """        # D14_thread_safe_signal - skip SIGINT registration in worker threads
        try:
            signal.signal(signal.SIGINT, self.signal_handler)
        except ValueError:
            pass  # not in main thread; main thread owns SIGINT"""

if old not in src:
    raise SystemExit("D14 anchor not found")
src = src.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D14: signal registration is now thread-safe")
