import sys, threading, traceback
sys.path.append("src")
from target_focused_bot import UnifiedTradingBot

errors = []
def make_bot(mkt):
    try:
        b = UnifiedTradingBot(mkt)
        print(f"  [{mkt}] instantiated OK in thread")
    except Exception as e:
        errors.append((mkt, str(e)))
        traceback.print_exc()

t1 = threading.Thread(target=make_bot, args=("NIFTY",))
t2 = threading.Thread(target=make_bot, args=("SENSEX",))
t1.start(); t2.start(); t1.join(); t2.join()

if errors:
    print("FAILED:", errors)
else:
    print("Thread-safe instantiation PASSED for both markets")
