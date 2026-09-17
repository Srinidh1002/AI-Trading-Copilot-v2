"""D14b - guard SIGTERM registration for thread-safety.

D14 fixed SIGINT. This handles the sibling SIGTERM call.
"""
path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

if "D14b_thread_safe_sigterm" in src:
    print("D14b already applied")
    raise SystemExit(0)

old = "        signal.signal(signal.SIGTERM, self.signal_handler)"
new = """        # D14b_thread_safe_sigterm - skip SIGTERM registration in worker threads
        try:
            signal.signal(signal.SIGTERM, self.signal_handler)
        except ValueError:
            pass  # not in main thread; main thread owns SIGTERM"""

if old not in src:
    raise SystemExit("D14b anchor not found")
src = src.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("D14b: SIGTERM registration is now thread-safe")
