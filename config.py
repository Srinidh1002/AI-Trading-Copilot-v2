import os
from pathlib import Path
from dotenv import load_dotenv

# ==========================================================
# Load Environment Variables
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

# ==========================================================
# Application
# ==========================================================

APP_NAME = "AI Trading Copilot"

VERSION = "2.0"

DEBUG = True

TIMEZONE = "Asia/Kolkata"

# ==========================================================
# Database
# ==========================================================

DATABASE_FOLDER = BASE_DIR / "database"

DATABASE_FOLDER.mkdir(exist_ok=True)

DATABASE_PATH = DATABASE_FOLDER / "ai_trading.db"

# ==========================================================
# Reports
# ==========================================================

REPORT_FOLDER = BASE_DIR / "reports"

REPORT_FOLDER.mkdir(exist_ok=True)

# ==========================================================
# Logs
# ==========================================================

LOG_FOLDER = BASE_DIR / "logs"

LOG_FOLDER.mkdir(exist_ok=True)

LOG_FILE = LOG_FOLDER / "application.log"

# ==========================================================
# Angel One SmartAPI
# ==========================================================

ANGEL_API_KEY = os.getenv("ANGEL_API_KEY", "")

ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID", "")

ANGEL_PIN = os.getenv("ANGEL_PIN", "")

ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "")

# Backward Compatibility

SMART_API_KEY = ANGEL_API_KEY

SMART_CLIENT_ID = ANGEL_CLIENT_ID

SMART_PASSWORD = ANGEL_PIN

SMART_TOTP = ANGEL_TOTP_SECRET

# ==========================================================
# Upstox
# ==========================================================

UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY", "")

UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET", "")

REDIRECT_URI = os.getenv("REDIRECT_URI", "")

# ==========================================================
# OpenAI
# ==========================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ==========================================================
# Dashboard Defaults
# ==========================================================

DEFAULT_SYMBOL = "^NSEI"

DEFAULT_INTERVAL = "5m"

DEFAULT_PERIOD = "1d"

REFRESH_SECONDS = 10

# ==========================================================
# Trading Configuration
# ==========================================================

DEFAULT_CAPITAL = 100000

RISK_PER_TRADE = 0.02

MAX_DAILY_LOSS = 0.05

MAX_OPEN_TRADES = 1

BROKER = "PAPER"

# ==========================================================
# Indicator Settings
# ==========================================================

EMA_FAST = 20

EMA_SLOW = 50

EMA_LONG = 200

RSI_PERIOD = 14

ADX_PERIOD = 14

ATR_PERIOD = 14

MACD_FAST = 12

MACD_SLOW = 26

MACD_SIGNAL = 9

SUPERTREND_PERIOD = 10

SUPERTREND_MULTIPLIER = 3

# ==========================================================
# Confidence Engine
# ==========================================================

BUY_THRESHOLD = 75

SELL_THRESHOLD = 75

HOLD_THRESHOLD = 60

# ==========================================================
# Paper Trading
# ==========================================================

ENABLE_PAPER_TRADING = True

ENABLE_LIVE_TRADING = False

# ==========================================================
# Logging
# ==========================================================

LOG_LEVEL = "INFO"

SAVE_DECISIONS = True

SAVE_MARKET_DATA = True

SAVE_REPORTS = True

# ==========================================================
# Future Features
# ==========================================================

ENABLE_OPTIONS_ENGINE = False

ENABLE_NEWS_ENGINE = False

ENABLE_SENTIMENT_ENGINE = False

ENABLE_AI_ENGINE = False

ENABLE_LEARNING_ENGINE = False

ENABLE_FII_DII_ENGINE = False