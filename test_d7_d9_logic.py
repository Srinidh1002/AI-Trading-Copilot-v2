"""D7+D9 unit test — simulate a trade progression and print trail behavior."""
import sys
sys.path.append("src")

# Create a minimal fake bot (no network, no state)
from target_focused_bot import UnifiedTradingBot
bot = UnifiedTradingBot("NIFTY")

# Simulate the trail logic in isolation (mirror the code we just inserted)
def simulate(entry, t1_lot_pct, bid_path):
    """
    entry: float — entry price
    t1_lot_pct: float — LTP % at which T1 activates (15.0)
    bid_path: list of bids observed (after entry)
    """
    floor = entry * 1.10
    t1_hit = False
    trail = None
    peak_bid = None
    exits = []
    for i, bid in enumerate(bid_path):
        if peak_bid is None or bid > peak_bid:
            peak_bid = bid
        ltp_pct_at_this_bid = ((bid - entry) / entry) * 100
        if not t1_hit and ltp_pct_at_this_bid >= t1_lot_pct:
            t1_hit = True
            trail = max(floor, peak_bid * 0.95)
            print(f"  step {i}: bid={bid:7.2f} ltp_pct={ltp_pct_at_this_bid:+6.2f}% [T1 ACTIVE] trail={trail:.2f}")
            continue
        if t1_hit and peak_bid:
            cand = max(floor, peak_bid * 0.95)
            if cand > trail: trail = cand
        status = f"trail={trail:.2f}" if t1_hit else "no trail"
        print(f"  step {i}: bid={bid:7.2f} ltp_pct={ltp_pct_at_this_bid:+6.2f}% {status}")
        if t1_hit and bid <= trail:
            exits.append((i, bid, trail, "TRAIL_STOP"))
            print(f"          ^^ EXIT at {bid:.2f} (trail stop {trail:.2f})")
            break
    return exits

print("=" * 70)
print("Scenario 1: entry=100, T1 at 115, straight up to T3 zone then reverse")
print("=" * 70)
bids = [100, 102, 105, 108, 112, 115, 118, 125, 135, 145, 155, 152, 148, 145, 140]
simulate(100.0, 15.0, bids)

print()
print("=" * 70)
print("Scenario 2: entry=100, hits T1 (+15%), then drifts back slowly")
print("=" * 70)
bids = [100, 105, 110, 115, 118, 120, 122, 120, 118, 116, 114, 112, 110, 108]
simulate(100.0, 15.0, bids)

print()
print("=" * 70)
print("Scenario 3: entry=100, spikes to +16% briefly then collapses")
print("=" * 70)
bids = [100, 105, 110, 116, 108, 102, 98, 95, 92, 90]
simulate(100.0, 15.0, bids)
