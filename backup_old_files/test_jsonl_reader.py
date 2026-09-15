# test_jsonl_reader.py

import json
from pathlib import Path
from datetime import datetime

print("🔍 Testing JSONL reader...")
print("=" * 60)

# Find the latest JSONL file
jsonl_files = list(Path('data/task9/live_stream').glob('ticks-*.jsonl'))
if jsonl_files:
    latest = sorted(jsonl_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
    print(f'📄 Reading: {latest.name}')
    print(f'📏 Size: {latest.stat().st_size} bytes')
    
    # Read and analyze
    nifty_data = []
    sensex_data = []
    
    with open(latest, 'r') as f:
        lines = f.readlines()
        print(f'📊 Total lines: {len(lines)}')
        
        # Check last 10 lines for symbols
        print('\n📋 Last 10 lines:')
        for line in lines[-10:]:
            try:
                data = json.loads(line.strip())
                symbol = data.get('tradingsymbol') or data.get('symbol', 'unknown')
                ltp = data.get('ltp') or data.get('LTP') or data.get('last_price', 0)
                print(f'  {symbol}: {ltp}')
                
                # Collect data
                if 'NIFTY' in str(symbol) or 'nifty' in str(symbol).lower():
                    nifty_data.append(ltp)
                elif 'SENSEX' in str(symbol) or 'sensex' in str(symbol).lower():
                    sensex_data.append(ltp)
            except Exception as e:
                print(f'  Error: {e}')
                print(f'  {line[:100]}...')
    
    # Show summary
    print('\n📊 Data Summary:')
    if nifty_data:
        print(f'  NIFTY: {len(nifty_data)} readings, latest: {nifty_data[-1]}')
    else:
        print('  NIFTY: No data found')
    
    if sensex_data:
        print(f'  SENSEX: {len(sensex_data)} readings, latest: {sensex_data[-1]}')
    else:
        print('  SENSEX: No data found')
        
    print('\n💡 The data exists! The bridge just needs to parse it correctly.')
else:
    print('❌ No JSONL files found')
