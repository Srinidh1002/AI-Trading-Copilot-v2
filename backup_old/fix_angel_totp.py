# fix_angel_totp.py
# Angel One TOTP Fix - They use a specific TOTP format

import os
import time
import pyotp
import requests
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("  ANGEL ONE TOTP FIX")
print("=" * 60)
print()

api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
client_id = os.getenv('ANGEL_CLIENT_ID', '')
pin = os.getenv('ANGEL_PIN', '')
totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')

print(f"API Key: {api_key[:8]}...")
print(f"Client ID: {client_id}")
print(f"PIN: {'SET' if pin else 'MISSING'}")
print(f"TOTP Secret: {'SET' if totp_secret else 'MISSING'}")
print()

if not totp_secret:
    print("❌ TOTP Secret is MISSING in .env")
    print("Please add: ANGEL_TOTP_SECRET=your_totp_secret")
    print()
    print("How to get TOTP Secret:")
    print("1. Login to Angel One web")
    print("2. Go to Profile -> Security -> Two Factor Authentication")
    print("3. Get the TOTP secret key")
    exit()

# Generate TOTP
print("Generating TOTP...")
try:
    totp = pyotp.TOTP(totp_secret)
    current_totp = totp.now()
    print(f"Current TOTP: {current_totp}")
    print(f"Time remaining: {30 - (int(time.time()) % 30)} seconds")
except Exception as e:
    print(f"❌ TOTP generation failed: {e}")
    print("The TOTP secret might be in the wrong format")
    print("Format should be: 5QTH5XXUR3PMCZ7J25A2RKALUA")
    exit()

print()
print("Testing login with TOTP...")

# Try login
url = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
headers = {
    "Content-Type": "application/json",
    "X-UserType": "USER",
    "X-SourceID": "WEB",
    "X-ClientLocalIP": "127.0.0.1",
    "X-ClientPublicIP": "127.0.0.1",
    "X-MACAddress": "00:00:00:00:00:00",
    "X-PrivateKey": api_key
}

data = {
    "clientcode": client_id,
    "password": pin,
    "totp": current_totp
}

response = requests.post(url, headers=headers, json=data, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    try:
        result = response.json()
        if result.get('status'):
            print("✅ LOGIN SUCCESSFUL!")
            print(f"Session Token: {result.get('data', {}).get('session_token', '')[:30]}...")
            print(f"Feed Token: {result.get('data', {}).get('feed_token', '')[:30]}...")
            
            # Save token
            import json
            from pathlib import Path
            token_file = Path("data/angel_token.json")
            token_file.parent.mkdir(parents=True, exist_ok=True)
            tokens = {
                'session_token': result.get('data', {}).get('session_token'),
                'feed_token': result.get('data', {}).get('feed_token'),
                'refresh_token': result.get('data', {}).get('refresh_token'),
                'expires_at': time.time() + 86400
            }
            with open(token_file, 'w') as f:
                json.dump(tokens, f)
            print("✅ Token saved to data/angel_token.json")
        else:
            print(f"❌ Login failed: {result.get('message', 'Unknown error')}")
            print(f"Error Code: {result.get('errorcode', 'N/A')}")
    except:
        print(f"❌ Invalid response: {response.text[:200]}")
else:
    print(f"❌ HTTP Error: {response.status_code}")
    print(f"Response: {response.text[:200]}")

print()
print("=" * 60)
