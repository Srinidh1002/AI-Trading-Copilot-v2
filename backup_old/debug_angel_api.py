# debug_angel_api.py
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# Get credentials
api_key = os.getenv('ANGEL_API_KEY', '') or os.getenv('ANGEL_APIKEY', '')
client_id = os.getenv('ANGEL_CLIENT_ID', '')
pin = os.getenv('ANGEL_PIN', '')
totp = os.getenv('ANGEL_TOTP_SECRET', '')

print("=" * 60)
print("  ANGEL ONE API DEBUG")
print("=" * 60)
print()

print(f"API Key: {api_key[:8] if api_key else 'MISSING'}...")
print(f"Client ID: {client_id}")
print(f"PIN: {'SET' if pin else 'MISSING'}")
print(f"TOTP: {'SET' if totp else 'MISSING'}")
print()

# Try different API endpoints
endpoints = [
    {
        "name": "Login",
        "url": "https://apiconnect.angelone.in/rest/auth/angelbroking/login/v1/products",
        "headers": {
            "Content-Type": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": api_key
        },
        "data": {
            "clientcode": client_id,
            "password": pin,
            "totp": totp
        }
    },
    {
        "name": "Login (Alternate)",
        "url": "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword",
        "headers": {
            "Content-Type": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": api_key
        },
        "data": {
            "clientcode": client_id,
            "password": pin,
            "totp": totp
        }
    }
]

for endpoint in endpoints:
    print(f"\nTesting: {endpoint['name']}")
    print(f"URL: {endpoint['url']}")
    print("-" * 40)
    
    try:
        response = requests.post(
            endpoint['url'], 
            headers=endpoint['headers'], 
            json=endpoint['data'], 
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response Text (first 500 chars):")
        print(response.text[:500])
        print()
        
        # Try to parse JSON
        try:
            data = response.json()
            print(f"JSON Parsed: {data}")
            if data.get('status'):
                print(f"✅ {endpoint['name']} SUCCESS!")
                print(f"Session Token: {data.get('data', {}).get('session_token', '')[:20]}...")
                break
            else:
                print(f"❌ {endpoint['name']} FAILED: {data.get('message', 'Unknown')}")
        except json.JSONDecodeError as e:
            print(f"❌ Not valid JSON: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print()
print("=" * 60)
print("If all endpoints failed, check:")
print("1. API Key is valid and active")
print("2. Client ID is correct")
print("3. PIN is correct")
print("4. TOTP secret is correct")
print("5. Your account is active")
print("=" * 60)
