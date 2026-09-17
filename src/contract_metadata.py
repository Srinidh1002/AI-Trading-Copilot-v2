"""Contract Metadata - Resolves lot size from instrument master.
Never hard-code lot sizes. Always lookup from current contract data.
"""
import json
from typing import Optional, Tuple


def build_lot_size_index(instruments: list) -> dict:
    """Build fast lookup: (symbol_prefix, expiry, strike_x100, type) -> lot_size
    
    Example key: ('NIFTY', '15SEP2026', 2360000, 'PE') -> 65
    """
    index = {}
    for inst in instruments:
        try:
            if inst.get('instrumenttype') != 'OPTIDX':
                continue
            sym = inst.get('symbol', '')
            expiry = inst.get('expiry', '')
            raw_strike = inst.get('strike', 0)
            if raw_strike is None:
                continue
            strike_key = int(float(raw_strike))
            lot = inst.get('lotsize', 0)
            if not lot or int(lot) <= 0:
                continue
            
            # Determine option type from symbol ending
            opt_type = None
            if sym.endswith('CE'):
                opt_type = 'CE'
            elif sym.endswith('PE'):
                opt_type = 'PE'
            else:
                continue
            
            # Determine market prefix
            market_prefix = None
            if sym.startswith('NIFTY') and not sym.startswith('BANKNIFTY') and not sym.startswith('FINNIFTY'):
                market_prefix = 'NIFTY'
            elif sym.startswith('SENSEX') and not sym.startswith('SENSEX50'):
                market_prefix = 'SENSEX'
            else:
                continue
            
            # Store by (market, expiry, strike_x100, type)
            key = (market_prefix, expiry, strike_key, opt_type)
            index[key] = int(lot)
        except Exception:
            continue
    
    return index


def resolve_lot_size(index: dict, market: str, expiry: str, 
                     strike: float, option_type: str) -> Tuple[Optional[int], str]:
    """Lookup lot size. Returns (lot_size, source) or (None, 'EVIDENCE_UNAVAILABLE').
    
    Args:
        index: built from build_lot_size_index()
        market: 'NIFTY' or 'SENSEX'
        expiry: e.g. '15SEP2026'
        strike: normalized strike (e.g. 23600 not 2360000)
        option_type: 'CE' or 'PE'
    """
    try:
        strike_key = int(round(strike * 100))
        key = (market.upper(), expiry, strike_key, option_type.upper())
        lot = index.get(key)
        if lot and lot > 0:
            return lot, 'instrument_master'
    except Exception:
        pass
    return None, 'EVIDENCE_UNAVAILABLE'


def load_contract_index(instruments_file: str = 'data/instruments.json') -> dict:
    """Load and build index from instruments file."""
    with open(instruments_file, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return build_lot_size_index(raw)


if __name__ == '__main__':
    # Self-test
    index = load_contract_index()
    print(f'Index size: {len(index)}')
    
    # Test NIFTY lookup
    lot, src = resolve_lot_size(index, 'NIFTY', '15SEP2026', 23600, 'PE')
    print(f'NIFTY 15SEP2026 23600 PE: lot={lot} source={src}')
    
    # Test SENSEX lookup
    lot, src = resolve_lot_size(index, 'SENSEX', '17SEP2026', 74900, 'CE')
    print(f'SENSEX 17SEP2026 74900 CE: lot={lot} source={src}')
