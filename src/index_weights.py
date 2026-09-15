"""Load index weights from snapshot file"""
import json
import os


def load_index_weights(market='NIFTY'):
    """Load weights for a specific market from snapshot file"""
    snapshot_file = 'data/index_constituent_snapshot.json'
    
    if not os.path.exists(snapshot_file):
        return get_default_weights(market)
    
    try:
        with open(snapshot_file, 'r') as f:
            snapshot = json.load(f)
        
        market_data = snapshot.get('markets', {}).get(market, {})
        weights = market_data.get('weights', {})
        
        if weights:
            # Return as list of (symbol, weight) tuples
            return list(weights.items()), market_data.get('selected_universe_coverage_pct', 0)
    except Exception:
        pass
    
    return get_default_weights(market)


def get_default_weights(market='NIFTY'):
    """Fallback weights"""
    if market == 'NIFTY':
        return [
            ('HDFCBANK-EQ', 10.56), ('ICICIBANK-EQ', 8.32), ('RELIANCE-EQ', 8.27),
            ('BHARTIARTL-EQ', 5.20), ('LT-EQ', 4.43), ('SBIN-EQ', 3.98),
            ('INFY-EQ', 3.61), ('AXISBANK-EQ', 3.39), ('KOTAKBANK-EQ', 2.80),
            ('M&M-EQ', 2.66),
        ], 52.8
    else:
        return [
            ('HDFCBANK-EQ', 12.91), ('RELIANCE-EQ', 10.64), ('ICICIBANK-EQ', 9.93),
            ('BHARTIARTL-EQ', 5.91), ('LT-EQ', 5.16), ('SBIN-EQ', 4.67),
            ('INFY-EQ', 4.43), ('AXISBANK-EQ', 3.95), ('KOTAKBANK-EQ', 3.42),
            ('M&M-EQ', 3.18),
        ], 64.1


def get_coverage_pct(market='NIFTY'):
    """Return how much of the index our universe covers"""
    _, coverage = load_index_weights(market)
    return coverage
