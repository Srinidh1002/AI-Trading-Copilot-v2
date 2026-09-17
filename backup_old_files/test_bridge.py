# test_bridge.py

import asyncio
import logging
from services.market.websocket_bridge import WebSocketBridge

logging.basicConfig(level=logging.INFO)

async def test_bridge():
    print("=" * 60)
    print("🔍 Testing WebSocket Bridge")
    print("=" * 60)
    
    bridge = WebSocketBridge('data/task9/live_stream')
    bridge.initialize()
    
    # Read data
    print("\n📊 Reading data...")
    data = await bridge.read_latest_data()
    
    if data:
        print(f"✅ Found data for: {list(data.keys())}")
        for symbol, tick in data.items():
            print(f"\n📈 {symbol}:")
            print(f"  LTP: {tick['ltp']}")
            print(f"  Volume: {tick['volume']}")
            print(f"  Timestamp: {tick['timestamp']}")
            print(f"  File: {tick['file']}")
    else:
        print("❌ No data found")
        print("\n💡 Possible issues:")
        print("  - The JSONL file might have a different format")
        print("  - The symbol names might be different")
        print("  - The file might be empty or corrupted")

if __name__ == "__main__":
    asyncio.run(test_bridge())
