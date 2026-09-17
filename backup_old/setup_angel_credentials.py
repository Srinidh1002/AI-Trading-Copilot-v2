# setup_angel_credentials.py
# Set up Angel One API credentials

import json
import sys
import os
from pathlib import Path
import getpass

print("=" * 60)
print("  ANGEL ONE API CREDENTIAL SETUP")
print("=" * 60)
print()
print("This will set up your Angel One API credentials.")
print("You can get these from: https://www.angelone.in/developer")
print()

# Get credentials
api_key = input("API Key: ").strip()
client_id = input("Client ID: ").strip()
password = getpass.getpass("Password: ")
totp = input("TOTP Secret (optional): ").strip()

# Save to config
config_file = Path("data/angel_config.json")
config_file.parent.mkdir(parents=True, exist_ok=True)

config = {
    'api_key': api_key,
    'client_id': client_id,
    'password': password,
    'totp': totp,
    'updated_at': __import__('datetime').datetime.now().isoformat()
}

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print()
print("✅ Credentials saved to data/angel_config.json")
print()
print("Testing connection...")

# Test connection
try:
    from services.market.angel_one_api import AngelOneAPI
    api = AngelOneAPI(api_key, client_id, password, totp)
    
    if api.authenticate():
        print("✅ Authentication successful!")
        
        # Test getting LTP
        ltp = api.get_ltp("NIFTY")
        print(f"📊 NIFTY LTP: {ltp}")
        
        # Test option chain
        chain = api.get_option_chain("NIFTY")
        strikes = chain.get('strikes', [])
        print(f"📈 Option chain loaded: {len(strikes)} strikes")
        
        if strikes:
            atm = next((s for s in strikes if s.get('call_ltp', 0) > 0), None)
            if atm:
                print(f"   ATM Strike: {atm['strike']}")
                print(f"   CALL Premium: ₹{atm['call_ltp']:.2f}")
                print(f"   PUT Premium: ₹{atm['put_ltp']:.2f}")
                print(f"   PCR: {atm['pcr']:.2f}")
    else:
        print("❌ Authentication failed. Please check your credentials.")
        print("   Make sure:")
        print("   - API Key is valid")
        print("   - Client ID is correct")
        print("   - Password is correct")
        
except Exception as e:
    print(f"❌ Connection test failed: {e}")
