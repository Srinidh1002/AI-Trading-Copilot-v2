import os

from dotenv import load_dotenv

load_dotenv()

UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")

UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")

REDIRECT_URI = os.getenv("REDIRECT_URI")
ANGEL_API_KEY = os.getenv("ANGEL_API_KEY")
ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID")
ANGEL_PIN = os.getenv("ANGEL_PIN")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET")
# ==========================================================
# Default Dashboard Settings
# ==========================================================

DEFAULT_SYMBOL = "^NSEI"      # NIFTY 50 Index
DEFAULT_INTERVAL = "5m"
DEFAULT_PERIOD = "1d"