"""
Exchange Upstox authorization code for an access token.
"""

import requests

from config import (
    UPSTOX_API_KEY,
    UPSTOX_API_SECRET,
    REDIRECT_URI,
)

TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"


def get_access_token(auth_code):
    """
    Exchange the authorization code received after login
    for an Upstox access token.
    """

    payload = {
        "code": auth_code.strip(),
        "client_id": UPSTOX_API_KEY,
        "client_secret": UPSTOX_API_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    headers = {
        "accept": "application/json",
        "Api-Version": "2.0",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    print("\n========== TOKEN REQUEST ==========")
    print("Client ID:", UPSTOX_API_KEY)
    print("Redirect URI:", REDIRECT_URI)
    print("Authorization Code:", auth_code)
    print("===================================\n")

    response = requests.post(
        TOKEN_URL,
        headers=headers,
        data=payload,
        timeout=30,
    )

    print("Status Code:", response.status_code)
    print("Response:")
    print(response.text)

    response.raise_for_status()

    token_data = response.json()

    print("\n✅ Access Token Generated Successfully!\n")

    return token_data