"""
Upstox Authentication
"""

import urllib.parse

from config import (
    UPSTOX_API_KEY,
    REDIRECT_URI,
)


def login_url():

    params = {
        "client_id": UPSTOX_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
    }

    return (
        "https://api.upstox.com/v2/login/authorization/dialog?"
        + urllib.parse.urlencode(params)
    )