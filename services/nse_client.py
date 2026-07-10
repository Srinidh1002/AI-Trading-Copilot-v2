"""
NSE Client
Handles session creation and requests to the NSE website.
"""

import requests

BASE_URL = "https://www.nseindia.com"
OPTION_CHAIN_API = "https://www.nseindia.com/api/option-chain-indices"


class NSEClient:

    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/137.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/option-chain",
        })

        # Initialize cookies
        self.session.get(BASE_URL, timeout=10)

    def option_chain(self, symbol):

        url = f"{OPTION_CHAIN_API}?symbol={symbol}"

        response = self.session.get(
            url,
            timeout=15
        )

        response.raise_for_status()

        return response.json()