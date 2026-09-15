# test_angel_connection.py - Updated to check both variable names
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("  ANGEL ONE CONNECTION TEST")
print("=" * 60)
print()

# Check .env variables - CHECK BOTH NAMES
api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
client_id = os.getenv('ANGEL_CLIENT_ID', '')
pin = os.getenv('ANGEL_PIN', '')
totp = os.getenv('ANGEL_TOTP_SECRET', '')

print(f"API Key: {api_key[:8] if api_key else 'MISSING'}...")
print(f"Client ID: {client_id if client_id else 'MISSING'}")
print(f"PIN: {'SET' if pin else 'MISSING'}")
print(f"TOTP: {'SET' if totp else 'MISSING'}")
print()

if not all([api_key, client_id, pin]):
    print("❌ Missing credentials in .env")
    print()
    print("Please add these to your .env file:")
    print("ANGEL_API_KEY=your_api_key_here")
    print("ANGEL_CLIENT_ID=your_client_id_here")
    print("ANGEL_PIN=your_pin_here")
    print("ANGEL_TOTP_SECRET=your_totp_here")
    print()
    print("Your .env currently has:")
    print(f"  ANGEL_API_KEY: {'SET' if os.getenv('ANGEL_API_KEY') else 'MISSING'}")
    print(f"  ANGEL_CLIENT_ID: {'SET' if os.getenv('ANGEL_CLIENT_ID') else 'MISSING'}")
    print(f"  ANGEL_PIN: {'SET' if os.getenv('ANGEL_PIN') else 'MISSING'}")
    print(f"  ANGEL_TOTP_SECRET: {'SET' if os.getenv('ANGEL_TOTP_SECRET') else 'MISSING'}")
    sys.exit(1)

try:
    from services.market.angel_one_api import AngelOneAPI
    
    print("Initializing Angel One API...")
    api = AngelOneAPI()
    
    print("Authenticating...")
    if api.authenticate():
        print("✅ Connected to Angel One successfully!")
        print()
        
        # Get NIFTY LTP
        nifty = api.get_ltp('NIFTY')
        print(f"NIFTY LTP: {nifty:,.2f}")
        
        # Get SENSEX LTP
        sensex = api.get_ltp('SENSEX')
        print(f"SENSEX LTP: {sensex:,.2f}")
        print()
        
        # Get option chain
        print("Fetching NIFTY Option Chain...")
        chain = api.get_option_chain('NIFTY')
        strikes = chain.get('strikes', [])
        print(f"Option Chain: {len(strikes)} strikes loaded")
        print(f"PCR: {chain.get('total_pcr', 0):.2f}")
        
        if strikes:
            # Show ATM
            underlying = chain.get('underlying', 0)
            atm = min(strikes, key=lambda s: abs(s['strike'] - underlying))
            print()
            print("ATM Strike Data:")
            print(f"  Strike: {atm['strike']}")
            print(f"  CALL LTP: ₹{atm.get('call_ltp', 0):.2f}")
            print(f"  PUT LTP: ₹{atm.get('put_ltp', 0):.2f}")
            print(f"  PCR: {atm.get('pcr', 0):.2f}")
            print(f"  CALL OI: {atm.get('call_oi', 0):,}")
            print(f"  PUT OI: {atm.get('put_oi', 0):,}")
        
        print()
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    else:
        print("❌ Authentication failed")
        print("Please check your credentials in .env")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
