# simple_angel_test.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Get credentials
api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
client_id = os.getenv('ANGEL_CLIENT_ID', '')
pin = os.getenv('ANGEL_PIN', '')
totp = os.getenv('ANGEL_TOTP_SECRET', '')

print("=" * 60)
print("  SIMPLE ANGEL ONE API TEST")
print("=" * 60)
print()
print(f"API Key: {api_key[:8] if api_key else 'MISSING'}...")
print(f"Client ID: {client_id}")
print()

if not api_key or not client_id:
    print("❌ Missing credentials")
    exit()

# Try login
url = "https://apiconnect.angelone.in/rest/auth/angelbroking/login/v1/products"
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
    "totp": totp
}

print("Attempting login...")
try:
    response = requests.post(url, headers=headers, json=data, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Success: {result.get('status', False)}")
        if result.get('status'):
            print("✅ Login successful!")
            print(f"Session Token: {result.get('data', {}).get('session_token', '')[:20]}...")
        else:
            print(f"❌ Login failed: {result.get('message', 'Unknown error')}")
    else:
        print(f"❌ HTTP Error: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {e}")
