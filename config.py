import os

from dotenv import load_dotenv

load_dotenv()

UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")

UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")

REDIRECT_URI = os.getenv("REDIRECT_URI")